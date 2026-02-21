from attendance.models import AttendanceSession, AttendanceRecord
from accounts.models import StudentProfile, BatchCourse
from courses.models import Subject
from django.contrib.auth import get_user_model
User = get_user_model()
import datetime

student = StudentProfile.objects.first()
print("Student found:", bool(student))
if not student:
    print("No student profiles in DB — aborting.")
else:
    subjects = Subject.objects.filter(course__batch_courses__batch=student.batch)
    print("Subjects for student batch:", subjects.count())
    subj = None
    if subjects.exists():
        subj = subjects.first()
    else:
        subj = Subject.objects.first()
        if subj:
            print("Linking course", subj.course, "to batch", student.batch)
            BatchCourse.objects.get_or_create(batch=student.batch, course=subj.course, defaults={'added_by': student.user})
    if not subj:
        print("No subjects available; cannot create session.")
    else:
        teacher = subj.teacher or User.objects.filter(role='teacher').first()
        if not teacher:
            print("No teacher users available; cannot assign teacher.")
        else:
            today = datetime.date.today()
            try:
                session, created = AttendanceSession.objects.get_or_create(
                    batch=student.batch,
                    subject=subj,
                    teacher=teacher,
                    date=today,
                    defaults={
                        'session_id': 'TEST-' + today.strftime('%Y%m%d'),
                        'status': 'completed',
                        'start_time': datetime.datetime.now().time()
                    }
                )
            except Exception as e:
                print('Error creating session:', e)
                session = None
                created = False

            if session:
                if created:
                    print('Created session', session.session_id)
                else:
                    session.status = 'completed'
                    session.save()
                    print('Found existing session', session.session_id)

                rec, rcreated = AttendanceRecord.objects.get_or_create(
                    session=session,
                    student=student,
                    defaults={'status':'present','recorded_by': teacher, 'date': today}
                )
                if rcreated:
                    print('Created attendance record for student', student.student_id)
                else:
                    print('Attendance record already exists for this student')

                print('Session total students:', session.attendance_records.count())
                print('Total attendance records:', AttendanceRecord.objects.count())

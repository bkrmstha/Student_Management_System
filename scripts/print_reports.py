from attendance.models import AttendanceSession, AttendanceRecord
from accounts.models import StudentProfile
from courses.models import Subject

student = StudentProfile.objects.first()
print('Student:', student)
if not student:
    print('No student found')
else:
    subjects = Subject.objects.filter(course__batch_courses__batch=student.batch).distinct()
    print('Subjects count:', subjects.count())
    for subj in subjects:
        subj_total = AttendanceRecord.objects.filter(student=student, session__subject=subj).count()
        
        # Skip subjects with no recorded attendance (matching view logic)
        if subj_total == 0:
            continue
        
        present_count = AttendanceRecord.objects.filter(student=student, session__subject=subj, status='present').count()
        absent_count = AttendanceRecord.objects.filter(student=student, session__subject=subj, status='absent').count()
        pct = (present_count / subj_total * 100) if subj_total > 0 else 0
        print(subj.name, 'sessions=', subj_total, 'present=', present_count, 'absent=', absent_count, 'pct=', pct)

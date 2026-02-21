from accounts.models import User, GuardianStudentRelationship, StudentProfile, GuardianProfile
from attendance.models import AttendanceRecord

print("=== GUARDIAN DEBUG INFO ===")

# Check guardians
guardians = User.objects.filter(role='guardian')
print(f"\nTotal guardians: {guardians.count()}")
for g in guardians:
    print(f"  - {g.email} ({g.get_full_name})")

# Check guardian profiles
gp = GuardianProfile.objects.all()
print(f"\nTotal guardian profiles: {gp.count()}")
for g in gp:
    print(f"  - {g.user.email}")

# Check relationships
rels = GuardianStudentRelationship.objects.all()
print(f"\nTotal guardian-student relationships: {rels.count()}")
for rel in rels:
    print(f"  - Guardian: {rel.guardian.email}, Student: {rel.student.email} (Primary: {rel.is_primary})")

# Check students
students = StudentProfile.objects.all()
print(f"\nTotal students: {students.count()}")
for s in students:
    # Check if this student has any relationships
    rels_for_student = GuardianStudentRelationship.objects.filter(student=s.user).count()
    print(f"  - {s.student_id} ({s.user.email}) - Guardians: {rels_for_student}")

# Check attendance records
records = AttendanceRecord.objects.all()
print(f"\nTotal attendance records: {records.count()}")

print("\n=== END DEBUG ===")

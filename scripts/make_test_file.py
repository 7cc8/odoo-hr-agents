# scripts/make_test_file.py   الاستخدام: py scripts/make_test_file.py existing@email.com
import sys
from openpyxl import Workbook

existing = sys.argv[1]
CO, DEPT, JOB = "شركة النخبة الذكية للتقنية", "الإدارة العليا / الموارد البشرية", "أخصائي موارد بشرية"
H = ["name","work_email","work_phone","mobile_phone","job_title","company","department","job"]

wb = Workbook(); ws = wb.active; ws.title = "Employees"; ws.append(H)
rows = [
 ["سارة عبدالله","sara.test1@example.com","","+966500000101","",CO,DEPT,JOB],          # 2 accepted
 ["خالد فهد","khaled.test@example.com","","+966500000102","",CO,"قسم غير موجود",JOB],    # 3 reference_not_found
 ["منى سعيد","mona.test@example.com","","+966500000103","","شركة غير موجودة","",""],    # 4 reference_not_found
 ["أحمد موجود",existing,"","+966500000104","",CO,DEPT,JOB],                            # 5 duplicate_existing_employee
 ["فاطمة علي","fatima.example.com","","+966500000105","",CO,DEPT,JOB],                  # 6 invalid email
 ["عبدالرحمن ناصر","dup.test@example.com","","+966500000106","",CO,"",""],             # 7 duplicate_in_file
 ["عبدالرحمن ناصر الثاني","dup.test@example.com","","+966500000107","",CO,"",""],       # 8 duplicate_in_file
 ["ياسر تركي","","","","",CO,"",""],                                                    # 9 no email, no mobile
 ["بندر سالم","bandar.test@example.com","",966500000110,"",CO,DEPT,JOB],                # 10 numeric phone cell
 ["\u200fنورة خالد","noura.test@example.com","","٠٥٠٠٠٠٠٠١١١","",CO,DEPT,JOB],        # 11 Arabic digits + RLM
]
for r in rows: ws.append(r)
wb.save("test_employees_10.xlsx"); print("saved test_employees_10.xlsx")
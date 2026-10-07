from openpyxl import Workbook

HEADERS = [
    "name",
    "work_email",
    "work_phone",
    "mobile_phone",
    "job_title",
    "company",
    "department",
    "job",
]

ROWS = [
    [
        "ليان منصور",
        "batch5.layan.20261003@example.com",
        "+966115550501",
        "+966500555501",
        "محلل موارد بشرية",
        "شركة النخبة الذكية للتقنية",
        "الإدارة العليا / الموارد البشرية",
        "أخصائي موارد بشرية",
    ],
    [
        "مازن الحربي",
        "batch5.mazen.20261003@example.com",
        "",
        "+966500555502",
        "منسق موارد بشرية",
        "شركة النخبة الذكية للتقنية",
        "الإدارة العليا / الموارد البشرية",
        "أخصائي موارد بشرية",
    ],
    [
        "أمينة رحمن",
        "batch5.amina.20261003@example.com",
        "",
        "+966500555503",
        "مسؤول موارد بشرية",
        "شركة النخبة الذكية للتقنية",
        "الإدارة العليا / الموارد البشرية",
        "أخصائي موارد بشرية",
    ],
    [
        "سلمان العتيبي",
        "batch5.salman.20261003@example.com",
        "",
        "+966500555504",
        "موظف موارد بشرية",
        "شركة العقار الموحدة",
        "",
        "",
    ],
    [
        "نجلاء فهد",
        "batch5.najla.20261003@example.com",
        "+966115550505",
        "+966500555505",
        "أخصائي شؤون موظفين",
        "شركة النخبة الذكية للتقنية",
        "الإدارة العليا / الموارد البشرية",
        "أخصائي موارد بشرية",
    ],
]

workbook = Workbook()
sheet = workbook.active
sheet.title = "Employees"
sheet.append(HEADERS)
for row in ROWS:
    sheet.append(row)

workbook.save("samples/batch5_test_20261003.xlsx")
print("saved samples/batch5_test_20261003.xlsx")

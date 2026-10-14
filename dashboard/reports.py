import csv
import io
import openpyxl
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from datetime import datetime

from applications.models import Application
from interviews.models import InterviewSummary
from jobs.models import Job
from candidates.models import CandidateProfile

def get_report_data(report_type, start_date, end_date, user):
    """Fetches data based on report type and applies date/role filters."""
    data = []
    headers = []

    if report_type == 'INTERVIEW':
        qs = InterviewSummary.objects.all()
        if start_date: qs = qs.filter(created_at__gte=start_date)
        if end_date: qs = qs.filter(created_at__lte=end_date)
        if user.role == 'RECRUITER': qs = qs.filter(application__job__recruiter=user)
        elif user.role == 'COMPANY' and hasattr(user, 'owned_company'): qs = qs.filter(application__job__company=user.owned_company)

        headers = ['Candidate', 'Job', 'Comm Score', 'Tech Score', 'Conf Score', 'Recommendation', 'Date']
        for item in qs:
            data.append([
                item.application.candidate.user.get_full_name(),
                item.application.job.title,
                item.communication_score,
                item.technical_score,
                item.confidence_score,
                item.hiring_recommendation,
                item.created_at.strftime("%Y-%m-%d")
            ])
            
    elif report_type == 'HIRING':
        qs = Application.objects.all()
        if start_date: qs = qs.filter(updated_at__gte=start_date)
        if end_date: qs = qs.filter(updated_at__lte=end_date)
        if user.role == 'RECRUITER': qs = qs.filter(job__recruiter=user)
        elif user.role == 'COMPANY' and hasattr(user, 'owned_company'): qs = qs.filter(job__company=user.owned_company)

        headers = ['Candidate', 'Job', 'Status', 'Applied At', 'Last Updated']
        for app in qs:
            data.append([
                app.candidate.user.get_full_name(),
                app.job.title,
                app.get_status_display(),
                app.applied_at.strftime("%Y-%m-%d"),
                app.updated_at.strftime("%Y-%m-%d")
            ])

    elif report_type == 'CANDIDATE':
        qs = CandidateProfile.objects.all()
        if start_date: qs = qs.filter(user__date_joined__gte=start_date)
        if end_date: qs = qs.filter(user__date_joined__lte=end_date)

        headers = ['Name', 'Email', 'Skills', 'Experience (Yrs)', 'Joined']
        for cand in qs:
            skills_str = cand.skills if isinstance(cand.skills, str) else ", ".join(cand.skills) if cand.skills else ""
            data.append([
                cand.user.get_full_name(),
                cand.user.email,
                skills_str,
                cand.experience_years,
                cand.user.date_joined.strftime("%Y-%m-%d")
            ])
            
    return headers, data

def generate_csv_report(headers, data, filename):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in data:
        writer.writerow(row)
    return response

def generate_excel_report(headers, data, filename):
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Report Data"
    
    ws.append(headers)
    for row in data:
        ws.append(row)
        
    wb.save(response)
    return response

def generate_pdf_report(headers, data, title, filename):
    template = get_template('dashboard/report_pdf.html')
    context = {'headers': headers, 'data': data, 'title': title, 'date': datetime.now().strftime("%Y-%m-%d")}
    html = template.render(context)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
    
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Error generating PDF')
    return response

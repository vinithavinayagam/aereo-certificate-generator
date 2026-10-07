from pathlib import Path
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

engine = create_engine('sqlite:///./certificates.db', connect_args={'check_same_thread': False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
OUT = Path('generated_certificates'); OUT.mkdir(exist_ok=True)

class Job(Base):
    __tablename__='jobs'
    id=Column(Integer,primary_key=True)
    course_name=Column(String,nullable=False)
    event_name=Column(String,nullable=False)
    status=Column(String,default='queued')
    total=Column(Integer,default=0)
    successful=Column(Integer,default=0)
    failed=Column(Integer,default=0)
    certificates=relationship('Certificate',back_populates='job',cascade='all, delete-orphan')
class Certificate(Base):
    __tablename__='certificates'
    id=Column(Integer,primary_key=True)
    job_id=Column(Integer,ForeignKey('jobs.id'),nullable=False)
    name=Column(String,nullable=False)
    email=Column(String,nullable=False)
    status=Column(String,default='pending')
    path=Column(String,nullable=True)
    error=Column(String,nullable=True)
    job=relationship('Job',back_populates='certificates')
Base.metadata.create_all(engine)

def db():
    d=SessionLocal()
    try: yield d
    finally: d.close()
class Recipient(BaseModel):
    name:str=Field(min_length=2,max_length=100)
    email:EmailStr
class Request(BaseModel):
    course_name:str=Field(min_length=2,max_length=150)
    event_name:str=Field(min_length=2,max_length=150)
    recipients:list[Recipient]=Field(min_length=1,max_length=1000)

app=FastAPI(title='AEREO Certificate Generation API',version='1.0')
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5173','http://127.0.0.1:5173'],allow_methods=['*'],allow_headers=['*'])

def make_pdf(c, job):
    path=OUT/f'certificate_{c.id}.pdf'; w,h=landscape(A4); pdf=canvas.Canvas(str(path),pagesize=(w,h))
    pdf.setLineWidth(3); pdf.rect(35,35,w-70,h-70)
    pdf.setFont('Helvetica-Bold',30); pdf.drawCentredString(w/2,h-120,'CERTIFICATE OF COMPLETION')
    pdf.setFont('Helvetica',16); pdf.drawCentredString(w/2,h-175,'This certificate is proudly presented to')
    pdf.setFont('Helvetica-Bold',28); pdf.drawCentredString(w/2,h-235,c.name)
    pdf.setFont('Helvetica',16); pdf.drawCentredString(w/2,h-285,f'for successfully completing {job.course_name}')
    pdf.setFont('Helvetica',14); pdf.drawCentredString(w/2,h-330,f'Event: {job.event_name}')
    pdf.setFont('Helvetica',11); pdf.drawCentredString(w/2,75,'Certificate Generation API')
    pdf.save(); return str(path)

def process(job_id):
    d=SessionLocal(); job=d.get(Job,job_id)
    if not job: d.close(); return
    job.status='processing'; d.commit()
    for c in d.query(Certificate).filter_by(job_id=job_id).all():
        try:
            c.status='processing'; d.commit(); c.path=make_pdf(c,job); c.status='completed'; job.successful+=1
        except Exception as e:
            c.status='failed'; c.error=str(e); job.failed+=1
        d.commit()
    job.status='completed'; d.commit(); d.close()

@app.get('/')
def root(): return {'message':'AEREO Certificate Generation API','docs':'/docs'}
@app.post('/jobs',status_code=202)
def create(req:Request,bg:BackgroundTasks,d:Session=Depends(db)):
    j=Job(course_name=req.course_name,event_name=req.event_name,total=len(req.recipients)); d.add(j); d.commit(); d.refresh(j)
    for r in req.recipients: d.add(Certificate(job_id=j.id,name=r.name,email=str(r.email)))
    d.commit(); bg.add_task(process,j.id)
    return {'job_id':j.id,'status':j.status,'total':j.total}
@app.get('/jobs/{job_id}')
def status(job_id:int,d:Session=Depends(db)):
    j=d.get(Job,job_id)
    if not j: raise HTTPException(404,'Job not found')
    return {'job_id':j.id,'course_name':j.course_name,'event_name':j.event_name,'status':j.status,'total':j.total,'successful':j.successful,'failed':j.failed,'certificates':[{'certificate_id':c.id,'recipient_name':c.name,'recipient_email':c.email,'status':c.status,'error_message':c.error} for c in j.certificates]}
@app.get('/certificates/{certificate_id}')
def download(certificate_id:int,d:Session=Depends(db)):
    c=d.get(Certificate,certificate_id)
    if not c: raise HTTPException(404,'Certificate not found')
    if c.status!='completed': raise HTTPException(409,f'Certificate is not available: {c.status}')
    p=Path(c.path)
    if not p.exists(): raise HTTPException(404,'File not found')
    return FileResponse(str(p),media_type='application/pdf',filename=f'certificate_{c.id}.pdf')

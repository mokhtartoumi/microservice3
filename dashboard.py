from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from typing import List, Optional
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
from fastapi.responses import JSONResponse
from collections import defaultdict

# Initialize Firebase
cred = credentials.Certificate("./serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Helper functions
async def get_problems():
    problems_ref = db.collection("problems")
    docs = problems_ref.stream()
    return [doc.to_dict() for doc in docs]

async def get_users(role: Optional[str] = None):
    users_ref = db.collection("users")
    if role:
        users_ref = users_ref.where("role", "==", role)
    docs = users_ref.stream()
    return [doc.to_dict() for doc in docs]

async def get_technicians():
    return await get_users("technicien")

async def get_assistants():
    return await get_users("assistant")

async def get_chefs():
    return await get_users("chef")

# Dashboard routes
@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    problems = await get_problems()
    technicians = await get_technicians()
    assistants = await get_assistants()
    chefs = await get_chefs()
    
    # Process data for charts
    status_counts = pd.DataFrame(problems)["status"].value_counts().reset_index()
    status_counts.columns = ["status", "count"]
    
    type_counts = pd.DataFrame(problems)["type"].value_counts().reset_index()
    type_counts.columns = ["type", "count"]
    
    # Create charts
    status_fig = px.pie(status_counts, values="count", names="status", title="Problem Status Distribution")
    type_fig = px.bar(type_counts, x="type", y="count", title="Problem Types")
    
    # Technician availability
    tech_availability = pd.DataFrame(technicians)["isAvailable"].value_counts().reset_index()
    tech_availability.columns = ["isAvailable", "count"]
    tech_availability["isAvailable"] = tech_availability["isAvailable"].apply(lambda x: "Available" if x else "Unavailable")
    availability_fig = px.pie(tech_availability, values="count", names="isAvailable", title="Technician Availability")
    
    # Problem timeline
    timeline_data = []
    for problem in problems:
        if "createdAt" in problem:
            timeline_data.append({
                "date": problem["createdAt"].strftime("%Y-%m-%d"),
                "type": problem.get("type", "unknown"),
                "status": problem.get("status", "unknown")
            })
    timeline_df = pd.DataFrame(timeline_data)
    if not timeline_df.empty:
        timeline_df["date"] = pd.to_datetime(timeline_df["date"])
        timeline_counts = timeline_df.groupby(["date", "type"]).size().reset_index(name="count")
        timeline_fig = px.line(timeline_counts, x="date", y="count", color="type", title="Problems Over Time")
        timeline_json = timeline_fig.to_json()
    else:
        timeline_json = None
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "problem_count": len(problems),
        "technician_count": len(technicians),
        "assistant_count": len(assistants),
        "chef_count": len(chefs),
        "status_chart": status_fig.to_json(),
        "type_chart": type_fig.to_json(),
        "availability_chart": availability_fig.to_json(),
        "timeline_chart": timeline_json,
        "problems": problems[:10],  # Show recent 10 problems
        "unassigned_problems": [p for p in problems if p.get("assignedTechnician") is None],
        "available_technicians": [t for t in technicians if t.get("isAvailable", False)]
    })

@router.get("/dashboard/problems")
async def problems_dashboard():
    problems = await get_problems()
    return {
        "total_problems": len(problems),
        "unassigned_problems": len([p for p in problems if p.get("assignedTechnician") is None]),
        "status_counts": pd.DataFrame(problems)["status"].value_counts().to_dict(),
        "type_counts": pd.DataFrame(problems)["type"].value_counts().to_dict()
    }

@router.get("/dashboard/users")
async def users_dashboard():
    technicians = await get_technicians()
    assistants = await get_assistants()
    chefs = await get_chefs()
    
    return {
        "technicians": {
            "total": len(technicians),
            "available": len([t for t in technicians if t.get("isAvailable", False)]),
            "unavailable": len([t for t in technicians if not t.get("isAvailable", True)]),
            "with_current_problem": len([t for t in technicians if t.get("currentProblem") is not None])
        },
        "assistants": {
            "total": len(assistants),
            "available": len([a for a in assistants if a.get("isAvailable", False)]),
            "sections": pd.DataFrame(assistants)["section"].value_counts().to_dict()
        },
        "chefs": {
            "total": len(chefs),
            "available": len([c for c in chefs if c.get("isAvailable", False)]),
            "places": pd.DataFrame(chefs)["place"].value_counts().to_dict()
        }
    }

@router.get("/dashboard/technicians")
async def technicians_dashboard():
    technicians = await get_technicians()
    problems = await get_problems()
    
    # Technician performance
    tech_performance = []
    for tech in technicians:
        tech_problems = [p for p in problems if p.get("assignedTechnician") == tech.get("email")]
        tech_performance.append({
            "name": tech.get("name"),
            "email": tech.get("email"),
            "total_problems": len(tech_problems),
            "solved": len([p for p in tech_problems if p.get("status") == "solved"]),
            "speciality": tech.get("speciality", "unknown")
        })
    
    return {
        "technicians": technicians,
        "performance": tech_performance
    }
@router.get("/dashboard/full-stats", response_class=JSONResponse)
async def full_stats_dashboard():
    problems = await get_problems()
    technicians = await get_technicians()
    assistants = await get_assistants()
    chefs = await get_chefs()
    
    # Problem statistics
    status_counts = pd.DataFrame(problems)["status"].value_counts().to_dict()
    type_counts = pd.DataFrame(problems)["type"].value_counts().to_dict()
    
    # Technician statistics
    tech_stats = {
        "total": len(technicians),
        "available": len([t for t in technicians if t.get("isAvailable", False)]),
        "by_speciality": pd.DataFrame(technicians)["speciality"].value_counts().to_dict(),
        "performance": []
    }
    
    # Problem resolution time (example - you'll need createdAt and resolvedAt in your data)
    resolution_times = []
    for problem in problems:
        if "createdAt" in problem and "resolvedAt" in problem:
            time_diff = (problem["resolvedAt"] - problem["createdAt"]).total_seconds() / 3600  # in hours
            resolution_times.append({
                "problem_id": problem.get("id"),
                "type": problem.get("type"),
                "resolution_hours": round(time_diff, 2)
            })
    
    # Weekly/Monthly trends
    timeline_data = []
    for problem in problems:
        if "createdAt" in problem:
            timeline_data.append({
                "date": problem["createdAt"].strftime("%Y-%m-%d"),
                "type": problem.get("type", "unknown"),
                "status": problem.get("status", "unknown")
            })
    
    return {
        "problems": {
            "total": len(problems),
            "unassigned": len([p for p in problems if p.get("assignedTechnician") is None]),
            "status_distribution": status_counts,
            "type_distribution": type_counts,
            "resolution_stats": {
                "average_hours": round(sum(t["resolution_hours"] for t in resolution_times) / len(resolution_times), 2) if resolution_times else 0,
                "fastest_resolution": min(t["resolution_hours"] for t in resolution_times) if resolution_times else 0,
                "slowest_resolution": max(t["resolution_hours"] for t in resolution_times) if resolution_times else 0
            }
        },
        "technicians": tech_stats,
        "assistants": {
            "total": len(assistants),
            "by_section": pd.DataFrame(assistants)["section"].value_counts().to_dict()
        },
        "chefs": {
            "total": len(chefs),
            "by_place": pd.DataFrame(chefs)["place"].value_counts().to_dict()
        },
        "timeline_data": timeline_data
    }

@router.get("/dashboard/problem-types")
async def problem_types_analysis():
    problems = await get_problems()
    df = pd.DataFrame(problems)
    
    if not df.empty:
        # Problem types by status
        type_status = df.groupby(['type', 'status']).size().unstack().fillna(0).to_dict()
        
        # Resolution time by type (if you have resolution data)
        return {
            "types_by_status": type_status,
            "stats_by_type": df.groupby('type').agg({
                # Add your metrics here
            }).to_dict()
        }
    return {}
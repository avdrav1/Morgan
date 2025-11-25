"""
API endpoints for metrics and monitoring.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, Dict, Any
from app.core.metrics import (
    metrics,
    get_check_in_response_rate,
    get_message_delivery_success_rate,
    get_task_completion_rate,
    get_rescheduling_frequency,
)
from app.core.alerts import alert_manager
from app.models.user import User
from app.api.auth import get_current_user

router = APIRouter()


@router.get("/metrics/summary")
async def get_metrics_summary(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get summary of key metrics for the current user.
    
    Returns:
        Dictionary with check-in response rate, task completion rate, and rescheduling frequency
    """
    user_id = str(current_user.id)
    
    return {
        "check_in_response_rate_percent": round(get_check_in_response_rate(user_id), 2),
        "task_completion_rate_percent": round(get_task_completion_rate(user_id), 2),
        "rescheduling_frequency": get_rescheduling_frequency(user_id),
        "message_delivery_success_rate_percent": round(get_message_delivery_success_rate(), 2),
    }


@router.get("/metrics/project/{project_id}")
async def get_project_metrics(
    project_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get metrics for a specific project.
    
    Args:
        project_id: The project ID
        
    Returns:
        Dictionary with project-specific metrics
    """
    user_id = str(current_user.id)
    
    return {
        "check_in_response_rate_percent": round(get_check_in_response_rate(user_id), 2),
        "task_completion_rate_percent": round(get_task_completion_rate(user_id, project_id), 2),
        "rescheduling_frequency": get_rescheduling_frequency(user_id, project_id),
    }


@router.get("/metrics/all")
async def get_all_metrics(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get all raw metrics data.
    
    Note: This endpoint is for debugging and monitoring purposes.
    
    Returns:
        Dictionary with all metrics counters and timers
    """
    # Only allow access to all metrics for admin users in production
    # For now, return all metrics
    return metrics.get_all_metrics()


@router.get("/alerts/history")
async def get_alert_history(
    limit: int = 50,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get recent alert history.
    
    Args:
        limit: Maximum number of alerts to return (default: 50)
        
    Returns:
        Dictionary with alert history and current failure counts
    """
    return {
        "alerts": alert_manager.get_alert_history(limit),
        "current_failure_counts": alert_manager.get_failure_counts(),
    }


@router.get("/health/detailed")
async def get_detailed_health(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get detailed health status including metrics and alerts.
    
    Returns:
        Dictionary with health status, metrics, and recent alerts
    """
    from app.core.database import check_database_health
    
    return {
        "status": "healthy",
        "database": "connected" if check_database_health() else "disconnected",
        "metrics": {
            "check_in_response_rate_percent": round(get_check_in_response_rate(), 2),
            "message_delivery_success_rate_percent": round(get_message_delivery_success_rate(), 2),
        },
        "failure_counts": alert_manager.get_failure_counts(),
        "recent_alerts": alert_manager.get_alert_history(10),
    }

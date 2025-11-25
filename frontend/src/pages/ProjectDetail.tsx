import React, { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { projectsAPI, tasksAPI } from '../services/api';
import {
  ArrowLeft,
  Calendar,
  CheckCircle,
  Clock,
  AlertCircle,
  Pause,
  Archive,
  Edit2,
  MessageSquare,
  TrendingUp,
} from 'lucide-react';
import { format, formatDistanceToNow, isPast, isFuture } from 'date-fns';

interface Task {
  id: string;
  title: string;
  description?: string;
  order: number;
  estimated_duration_hours?: number;
  due_date?: string;
  completed_at?: string;
  status: string;
  blocker_type?: string;
  blocker_description?: string;
  reschedule_count: number;
}

interface CheckIn {
  id: string;
  check_in_type: string;
  status: string;
  scheduled_for?: string;
  sent_at?: string;
  responded_at?: string;
  message_sent?: string;
  user_response?: string;
  assistant_reply?: string;
  blocker_detected: boolean;
  reschedule_initiated: boolean;
}

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [showCheckIns, setShowCheckIns] = useState(false);

  const { data: project, isLoading } = useQuery({
    queryKey: ['project', id],
    queryFn: async () => {
      const response = await projectsAPI.get(id!);
      return response.data;
    },
    enabled: !!id,
  });

  const { data: checkIns } = useQuery({
    queryKey: ['task-checkins', selectedTaskId],
    queryFn: async () => {
      const response = await tasksAPI.getCheckIns(selectedTaskId!);
      return response.data;
    },
    enabled: !!selectedTaskId && showCheckIns,
  });

  const completeTaskMutation = useMutation({
    mutationFn: (taskId: string) => tasksAPI.complete(taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project', id] });
    },
  });

  const pauseProjectMutation = useMutation({
    mutationFn: () => projectsAPI.pause(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project', id] });
    },
  });

  const archiveProjectMutation = useMutation({
    mutationFn: () => projectsAPI.archive(id!),
    onSuccess: () => {
      navigate('/');
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading project...</div>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Project not found</div>
      </div>
    );
  }

  const tasks: Task[] = project.tasks || [];
  const completedTasks = tasks.filter((t) => t.status === 'completed').length;
  const totalTasks = tasks.length;
  const progressPercentage = totalTasks > 0 ? (completedTasks / totalTasks) * 100 : 0;

  const upcomingTasks = tasks.filter(
    (t) => t.status !== 'completed' && t.due_date && isFuture(new Date(t.due_date))
  );
  const overdueTasks = tasks.filter(
    (t) => t.status !== 'completed' && t.due_date && isPast(new Date(t.due_date))
  );
  const blockedTasks = tasks.filter((t) => t.status === 'blocked');

  const getTaskStatusColor = (task: Task) => {
    if (task.status === 'completed') return 'bg-green-100 text-green-800 border-green-200';
    if (task.status === 'blocked') return 'bg-red-100 text-red-800 border-red-200';
    if (task.due_date && isPast(new Date(task.due_date)))
      return 'bg-orange-100 text-orange-800 border-orange-200';
    return 'bg-blue-100 text-blue-800 border-blue-200';
  };

  const getTaskStatusIcon = (task: Task) => {
    if (task.status === 'completed') return <CheckCircle className="w-5 h-5 text-green-600" />;
    if (task.status === 'blocked') return <AlertCircle className="w-5 h-5 text-red-600" />;
    if (task.due_date && isPast(new Date(task.due_date)))
      return <Clock className="w-5 h-5 text-orange-600" />;
    return <Clock className="w-5 h-5 text-blue-600" />;
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <button
            onClick={() => navigate('/')}
            className="flex items-center text-gray-600 hover:text-gray-900 mb-4"
          >
            <ArrowLeft className="w-5 h-5 mr-2" />
            Back to Dashboard
          </button>

          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center space-x-3 mb-2">
                <h1 className="text-3xl font-bold text-gray-900">{project.title}</h1>
                <span
                  className={`px-3 py-1 text-sm font-medium rounded-full ${
                    project.status === 'active'
                      ? 'bg-green-100 text-green-800'
                      : project.status === 'paused'
                      ? 'bg-yellow-100 text-yellow-800'
                      : project.status === 'completed'
                      ? 'bg-blue-100 text-blue-800'
                      : 'bg-gray-100 text-gray-800'
                  }`}
                >
                  {project.status}
                </span>
              </div>
              {project.goal && <p className="text-gray-600 mb-4">{project.goal}</p>}
              {project.target_completion_date && (
                <div className="flex items-center text-sm text-gray-500">
                  <Calendar className="w-4 h-4 mr-2" />
                  Target completion:{' '}
                  {format(new Date(project.target_completion_date), 'MMMM d, yyyy')}
                </div>
              )}
            </div>

            <div className="flex space-x-2">
              {project.status === 'active' && (
                <button
                  onClick={() => pauseProjectMutation.mutate()}
                  disabled={pauseProjectMutation.isPending}
                  className="flex items-center px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  <Pause className="w-4 h-4 mr-2" />
                  Pause
                </button>
              )}
              <button
                onClick={() => archiveProjectMutation.mutate()}
                disabled={archiveProjectMutation.isPending}
                className="flex items-center px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <Archive className="w-4 h-4 mr-2" />
                Archive
              </button>
            </div>
          </div>
        </div>

        {/* Progress Overview */}
        <div className="grid md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600">Progress</span>
              <TrendingUp className="w-5 h-5 text-blue-600" />
            </div>
            <div className="text-3xl font-bold text-gray-900 mb-2">
              {Math.round(progressPercentage)}%
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all"
                style={{ width: `${progressPercentage}%` }}
              />
            </div>
            <div className="text-sm text-gray-500 mt-2">
              {completedTasks} of {totalTasks} tasks
            </div>
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600">Upcoming</span>
              <Clock className="w-5 h-5 text-blue-600" />
            </div>
            <div className="text-3xl font-bold text-gray-900">{upcomingTasks.length}</div>
            <div className="text-sm text-gray-500 mt-2">tasks due soon</div>
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600">Overdue</span>
              <AlertCircle className="w-5 h-5 text-orange-600" />
            </div>
            <div className="text-3xl font-bold text-gray-900">{overdueTasks.length}</div>
            <div className="text-sm text-gray-500 mt-2">tasks past deadline</div>
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600">Blocked</span>
              <AlertCircle className="w-5 h-5 text-red-600" />
            </div>
            <div className="text-3xl font-bold text-gray-900">{blockedTasks.length}</div>
            <div className="text-sm text-gray-500 mt-2">tasks need help</div>
          </div>
        </div>

        {/* Timeline Visualization */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-6">Timeline</h2>

          <div className="space-y-4">
            {tasks
              .sort((a, b) => a.order - b.order)
              .map((task, index) => (
                <div key={task.id} className="relative">
                  {/* Timeline connector */}
                  {index < tasks.length - 1 && (
                    <div className="absolute left-6 top-12 w-0.5 h-full bg-gray-200" />
                  )}

                  <div
                    className={`flex items-start space-x-4 p-4 rounded-lg border-2 transition-all ${getTaskStatusColor(
                      task
                    )} ${
                      selectedTaskId === task.id ? 'ring-2 ring-blue-500' : ''
                    } hover:shadow-md cursor-pointer`}
                    onClick={() => {
                      setSelectedTaskId(task.id);
                      setShowCheckIns(false);
                    }}
                  >
                    {/* Status icon */}
                    <div className="flex-shrink-0 mt-1">{getTaskStatusIcon(task)}</div>

                    {/* Task content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between mb-2">
                        <h3 className="font-semibold text-gray-900">
                          {task.order}. {task.title}
                        </h3>
                        {task.status !== 'completed' && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              completeTaskMutation.mutate(task.id);
                            }}
                            className="ml-4 px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700 transition-colors"
                          >
                            Mark Complete
                          </button>
                        )}
                      </div>

                      {task.description && (
                        <p className="text-sm text-gray-600 mb-3">{task.description}</p>
                      )}

                      <div className="flex flex-wrap items-center gap-4 text-sm">
                        {task.estimated_duration_hours && (
                          <span className="flex items-center text-gray-600">
                            <Clock className="w-4 h-4 mr-1" />
                            {task.estimated_duration_hours}h estimated
                          </span>
                        )}

                        {task.due_date && (
                          <span className="flex items-center text-gray-600">
                            <Calendar className="w-4 h-4 mr-1" />
                            Due {format(new Date(task.due_date), 'MMM d, yyyy')}
                            {task.status !== 'completed' && (
                              <span className="ml-2 text-gray-500">
                                ({formatDistanceToNow(new Date(task.due_date), { addSuffix: true })})
                              </span>
                            )}
                          </span>
                        )}

                        {task.completed_at && (
                          <span className="flex items-center text-green-600">
                            <CheckCircle className="w-4 h-4 mr-1" />
                            Completed {format(new Date(task.completed_at), 'MMM d, yyyy')}
                          </span>
                        )}

                        {task.reschedule_count > 0 && (
                          <span className="text-orange-600">
                            Rescheduled {task.reschedule_count}x
                          </span>
                        )}
                      </div>

                      {task.blocker_type && (
                        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded">
                          <div className="flex items-center text-red-800 font-medium mb-1">
                            <AlertCircle className="w-4 h-4 mr-2" />
                            Blocker: {task.blocker_type}
                          </div>
                          {task.blocker_description && (
                            <p className="text-sm text-red-700">{task.blocker_description}</p>
                          )}
                        </div>
                      )}

                      {selectedTaskId === task.id && (
                        <div className="mt-4 pt-4 border-t border-gray-200">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setShowCheckIns(!showCheckIns);
                            }}
                            className="flex items-center text-blue-600 hover:text-blue-700 font-medium"
                          >
                            <MessageSquare className="w-4 h-4 mr-2" />
                            {showCheckIns ? 'Hide' : 'View'} Check-in History
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Check-in history */}
                  {selectedTaskId === task.id && showCheckIns && checkIns && (
                    <div className="ml-12 mt-4 space-y-3">
                      {checkIns.length === 0 ? (
                        <div className="p-4 bg-gray-50 rounded-lg text-sm text-gray-600">
                          No check-ins yet for this task
                        </div>
                      ) : (
                        checkIns.map((checkIn: CheckIn) => (
                          <div
                            key={checkIn.id}
                            className="p-4 bg-gray-50 rounded-lg border border-gray-200"
                          >
                            <div className="flex items-center justify-between mb-2">
                              <span className="text-sm font-medium text-gray-900">
                                {checkIn.check_in_type} Check-in
                              </span>
                              <span className="text-xs text-gray-500">
                                {checkIn.sent_at &&
                                  format(new Date(checkIn.sent_at), 'MMM d, yyyy h:mm a')}
                              </span>
                            </div>

                            {checkIn.message_sent && (
                              <div className="mb-3">
                                <div className="text-xs text-gray-500 mb-1">Assistant:</div>
                                <div className="text-sm text-gray-700 bg-white p-3 rounded">
                                  {checkIn.message_sent}
                                </div>
                              </div>
                            )}

                            {checkIn.user_response && (
                              <div className="mb-3">
                                <div className="text-xs text-gray-500 mb-1">You:</div>
                                <div className="text-sm text-gray-700 bg-blue-50 p-3 rounded">
                                  {checkIn.user_response}
                                </div>
                              </div>
                            )}

                            {checkIn.assistant_reply && (
                              <div className="mb-3">
                                <div className="text-xs text-gray-500 mb-1">Assistant:</div>
                                <div className="text-sm text-gray-700 bg-white p-3 rounded">
                                  {checkIn.assistant_reply}
                                </div>
                              </div>
                            )}

                            <div className="flex items-center space-x-4 text-xs text-gray-500">
                              <span
                                className={`px-2 py-1 rounded ${
                                  checkIn.status === 'responded'
                                    ? 'bg-green-100 text-green-800'
                                    : checkIn.status === 'sent'
                                    ? 'bg-blue-100 text-blue-800'
                                    : 'bg-gray-100 text-gray-800'
                                }`}
                              >
                                {checkIn.status}
                              </span>
                              {checkIn.blocker_detected && (
                                <span className="text-red-600">Blocker detected</span>
                              )}
                              {checkIn.reschedule_initiated && (
                                <span className="text-orange-600">Reschedule initiated</span>
                              )}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  )}
                </div>
              ))}
          </div>
        </div>
      </div>
    </div>
  );
}

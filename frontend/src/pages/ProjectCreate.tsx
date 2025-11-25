import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { projectsAPI } from '../services/api';
import { ArrowLeft, Send, CheckCircle, Edit2, Calendar } from 'lucide-react';

type ProjectCreationStep = 'description' | 'clarification' | 'review_tasks' | 'approve_timeline';

interface ClarificationQuestion {
  question: string;
  context?: string;
}

interface Task {
  title: string;
  description?: string;
  order: number;
  estimated_duration_hours?: number;
  due_date?: string;
}

export default function ProjectCreate() {
  const navigate = useNavigate();
  const [step, setStep] = useState<ProjectCreationStep>('description');
  const [projectDescription, setProjectDescription] = useState('');
  const [projectId, setProjectId] = useState<string | null>(null);
  const [clarificationQuestions, setClarificationQuestions] = useState<ClarificationQuestion[]>([]);
  const [clarificationAnswers, setClarificationAnswers] = useState<Record<string, string>>({});
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [proposedTasks, setProposedTasks] = useState<Task[]>([]);
  const [estimatedCompletionDate, setEstimatedCompletionDate] = useState<string | null>(null);
  const [totalEstimatedHours, setTotalEstimatedHours] = useState<number>(0);
  const [editingTaskIndex, setEditingTaskIndex] = useState<number | null>(null);

  const createProjectMutation = useMutation({
    mutationFn: (description: string) =>
      projectsAPI.create({ description, title: null, goal: null }),
    onSuccess: (response) => {
      const data = response.data;
      
      if (data.status === 'needs_clarification') {
        // Need clarification
        setProjectId(data.project_id);
        setClarificationQuestions(data.clarification_questions || []);
        setStep('clarification');
      } else {
        // Project created directly
        setProjectId(data.id);
        // Proceed to decompose
        decomposeProjectMutation.mutate(data.id);
      }
    },
  });

  const clarifyProjectMutation = useMutation({
    mutationFn: ({ projectId, answers }: { projectId: string; answers: Record<string, string> }) =>
      projectsAPI.clarify(projectId, answers),
    onSuccess: (response) => {
      const data = response.data;
      // After clarification, decompose the project
      decomposeProjectMutation.mutate(data.id);
    },
  });

  const decomposeProjectMutation = useMutation({
    mutationFn: (projectId: string) => projectsAPI.decompose(projectId),
    onSuccess: (response) => {
      const data = response.data;
      setProposedTasks(data.tasks || []);
      setEstimatedCompletionDate(data.estimated_completion_date);
      setTotalEstimatedHours(data.total_estimated_hours || 0);
      setStep('review_tasks');
    },
  });

  const approveTimelineMutation = useMutation({
    mutationFn: ({ projectId, tasks }: { projectId: string; tasks: Task[] }) =>
      projectsAPI.approveTimeline(projectId, true, tasks),
    onSuccess: (response) => {
      const data = response.data;
      navigate(`/projects/${data.id}`);
    },
  });

  const handleSubmitDescription = () => {
    if (projectDescription.trim()) {
      createProjectMutation.mutate(projectDescription);
    }
  };

  const handleAnswerQuestion = () => {
    if (currentQuestionIndex < clarificationQuestions.length - 1) {
      setCurrentQuestionIndex(currentQuestionIndex + 1);
    } else {
      // All questions answered, submit clarification
      if (projectId) {
        clarifyProjectMutation.mutate({ projectId, answers: clarificationAnswers });
      }
    }
  };

  const handlePreviousQuestion = () => {
    if (currentQuestionIndex > 0) {
      setCurrentQuestionIndex(currentQuestionIndex - 1);
    }
  };

  const handleUpdateTask = (index: number, field: keyof Task, value: any) => {
    const updatedTasks = [...proposedTasks];
    updatedTasks[index] = { ...updatedTasks[index], [field]: value };
    setProposedTasks(updatedTasks);
  };

  const handleApproveTimeline = () => {
    if (projectId) {
      approveTimelineMutation.mutate({ projectId, tasks: proposedTasks });
    }
  };

  const currentQuestion = clarificationQuestions[currentQuestionIndex];

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <button
            onClick={() => navigate('/')}
            className="flex items-center text-gray-600 hover:text-gray-900 mb-4"
          >
            <ArrowLeft className="w-5 h-5 mr-2" />
            Back to Dashboard
          </button>
          <h1 className="text-3xl font-bold text-gray-900">Create New Project</h1>
        </div>

        {/* Content */}
        <div className="bg-white rounded-lg shadow-md p-8">
          {step === 'description' && (
            <div>
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">
                What would you like to accomplish?
              </h2>
              <p className="text-gray-600 mb-6">
                Describe your goal in your own words. Don't worry about being too specific—I'll
                help you clarify the details.
              </p>

              <textarea
                value={projectDescription}
                onChange={(e) => setProjectDescription(e.target.value)}
                placeholder="Example: I want to build a mobile app for tracking daily habits..."
                className="w-full h-48 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              />

              <div className="mt-6 flex justify-end">
                <button
                  onClick={handleSubmitDescription}
                  disabled={!projectDescription.trim() || createProjectMutation.isPending}
                  className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
                >
                  {createProjectMutation.isPending ? (
                    'Processing...'
                  ) : (
                    <>
                      Continue
                      <Send className="w-5 h-5 ml-2" />
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {step === 'clarification' && currentQuestion && (
            <div>
              <div className="mb-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-2xl font-semibold text-gray-900">Let's clarify some details</h2>
                  <span className="text-sm text-gray-500">
                    Question {currentQuestionIndex + 1} of {clarificationQuestions.length}
                  </span>
                </div>
                
                {/* Progress bar */}
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all"
                    style={{
                      width: `${((currentQuestionIndex + 1) / clarificationQuestions.length) * 100}%`,
                    }}
                  />
                </div>
              </div>

              <div className="mb-6">
                <label className="block text-lg font-medium text-gray-900 mb-3">
                  {currentQuestion.question}
                </label>
                {currentQuestion.context && (
                  <p className="text-sm text-gray-600 mb-4">{currentQuestion.context}</p>
                )}
                <textarea
                  value={clarificationAnswers[currentQuestion.question] || ''}
                  onChange={(e) =>
                    setClarificationAnswers({
                      ...clarificationAnswers,
                      [currentQuestion.question]: e.target.value,
                    })
                  }
                  placeholder="Your answer..."
                  className="w-full h-32 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                />
              </div>

              <div className="flex justify-between">
                <button
                  onClick={handlePreviousQuestion}
                  disabled={currentQuestionIndex === 0}
                  className="px-6 py-3 text-gray-600 hover:text-gray-900 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Previous
                </button>
                <button
                  onClick={handleAnswerQuestion}
                  disabled={
                    !clarificationAnswers[currentQuestion.question]?.trim() ||
                    clarifyProjectMutation.isPending
                  }
                  className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
                >
                  {clarifyProjectMutation.isPending ? (
                    'Processing...'
                  ) : currentQuestionIndex < clarificationQuestions.length - 1 ? (
                    'Next'
                  ) : (
                    <>
                      Finish
                      <Send className="w-5 h-5 ml-2" />
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {step === 'review_tasks' && (
            <div>
              <div className="mb-6">
                <h2 className="text-2xl font-semibold text-gray-900 mb-2">
                  Review Your Project Plan
                </h2>
                <p className="text-gray-600">
                  I've broken down your project into {proposedTasks.length} tasks. You can edit any
                  details before approving.
                </p>
              </div>

              {/* Summary */}
              <div className="mb-6 p-4 bg-blue-50 rounded-lg">
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <div className="text-sm text-gray-600">Total Tasks</div>
                    <div className="text-2xl font-bold text-gray-900">{proposedTasks.length}</div>
                  </div>
                  <div>
                    <div className="text-sm text-gray-600">Estimated Hours</div>
                    <div className="text-2xl font-bold text-gray-900">{totalEstimatedHours}h</div>
                  </div>
                  {estimatedCompletionDate && (
                    <div className="md:col-span-2">
                      <div className="text-sm text-gray-600">Target Completion</div>
                      <div className="text-lg font-semibold text-gray-900">
                        {new Date(estimatedCompletionDate).toLocaleDateString('en-US', {
                          weekday: 'long',
                          year: 'numeric',
                          month: 'long',
                          day: 'numeric',
                        })}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Tasks list */}
              <div className="space-y-4 mb-6">
                {proposedTasks.map((task, index) => (
                  <div
                    key={index}
                    className="p-4 border border-gray-200 rounded-lg hover:border-gray-300 transition-colors"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1">
                        {editingTaskIndex === index ? (
                          <input
                            type="text"
                            value={task.title}
                            onChange={(e) => handleUpdateTask(index, 'title', e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-semibold"
                          />
                        ) : (
                          <h3 className="font-semibold text-gray-900">
                            {index + 1}. {task.title}
                          </h3>
                        )}
                      </div>
                      <button
                        onClick={() =>
                          setEditingTaskIndex(editingTaskIndex === index ? null : index)
                        }
                        className="ml-4 p-2 text-gray-500 hover:text-gray-700"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                    </div>

                    {editingTaskIndex === index ? (
                      <div className="space-y-3">
                        <textarea
                          value={task.description || ''}
                          onChange={(e) => handleUpdateTask(index, 'description', e.target.value)}
                          placeholder="Task description..."
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                          rows={2}
                        />
                        <div className="grid md:grid-cols-2 gap-3">
                          <div>
                            <label className="block text-sm text-gray-600 mb-1">
                              Estimated Hours
                            </label>
                            <input
                              type="number"
                              value={task.estimated_duration_hours || ''}
                              onChange={(e) =>
                                handleUpdateTask(
                                  index,
                                  'estimated_duration_hours',
                                  parseFloat(e.target.value) || 0
                                )
                              }
                              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                          </div>
                          <div>
                            <label className="block text-sm text-gray-600 mb-1">Due Date</label>
                            <input
                              type="date"
                              value={
                                task.due_date
                                  ? new Date(task.due_date).toISOString().split('T')[0]
                                  : ''
                              }
                              onChange={(e) =>
                                handleUpdateTask(
                                  index,
                                  'due_date',
                                  e.target.value ? new Date(e.target.value).toISOString() : null
                                )
                              }
                              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                          </div>
                        </div>
                      </div>
                    ) : (
                      <>
                        {task.description && (
                          <p className="text-sm text-gray-600 mb-2">{task.description}</p>
                        )}
                        <div className="flex items-center space-x-4 text-sm text-gray-500">
                          {task.estimated_duration_hours && (
                            <span>⏱️ {task.estimated_duration_hours}h</span>
                          )}
                          {task.due_date && (
                            <span className="flex items-center">
                              <Calendar className="w-4 h-4 mr-1" />
                              {new Date(task.due_date).toLocaleDateString()}
                            </span>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                ))}
              </div>

              <div className="flex justify-between">
                <button
                  onClick={() => setStep('description')}
                  className="px-6 py-3 text-gray-600 hover:text-gray-900 transition-colors"
                >
                  Start Over
                </button>
                <button
                  onClick={() => setStep('approve_timeline')}
                  className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center"
                >
                  Continue to Approval
                  <CheckCircle className="w-5 h-5 ml-2" />
                </button>
              </div>
            </div>
          )}

          {step === 'approve_timeline' && (
            <div>
              <div className="text-center mb-8">
                <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <CheckCircle className="w-10 h-10 text-blue-600" />
                </div>
                <h2 className="text-2xl font-semibold text-gray-900 mb-2">
                  Ready to Start Your Project?
                </h2>
                <p className="text-gray-600">
                  Once you approve, I'll start sending you proactive check-ins based on your
                  availability and task deadlines.
                </p>
              </div>

              <div className="bg-gray-50 rounded-lg p-6 mb-8">
                <h3 className="font-semibold text-gray-900 mb-4">What happens next:</h3>
                <ul className="space-y-3">
                  <li className="flex items-start">
                    <div className="w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center mr-3 mt-0.5 flex-shrink-0">
                      1
                    </div>
                    <div>
                      <div className="font-medium text-gray-900">Proactive Check-ins</div>
                      <div className="text-sm text-gray-600">
                        I'll reach out when you should be working on tasks, respecting your
                        availability
                      </div>
                    </div>
                  </li>
                  <li className="flex items-start">
                    <div className="w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center mr-3 mt-0.5 flex-shrink-0">
                      2
                    </div>
                    <div>
                      <div className="font-medium text-gray-900">Adaptive Support</div>
                      <div className="text-sm text-gray-600">
                        If you're stuck, I'll help diagnose blockers and suggest solutions
                      </div>
                    </div>
                  </li>
                  <li className="flex items-start">
                    <div className="w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center mr-3 mt-0.5 flex-shrink-0">
                      3
                    </div>
                    <div>
                      <div className="font-medium text-gray-900">Flexible Rescheduling</div>
                      <div className="text-sm text-gray-600">
                        Need to adjust? We'll have a conversation to find a new timeline that works
                      </div>
                    </div>
                  </li>
                </ul>
              </div>

              <div className="flex justify-between">
                <button
                  onClick={() => setStep('review_tasks')}
                  className="px-6 py-3 text-gray-600 hover:text-gray-900 transition-colors"
                >
                  Back to Review
                </button>
                <button
                  onClick={handleApproveTimeline}
                  disabled={approveTimelineMutation.isPending}
                  className="px-8 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
                >
                  {approveTimelineMutation.isPending ? (
                    'Creating Project...'
                  ) : (
                    <>
                      Approve & Start Project
                      <CheckCircle className="w-5 h-5 ml-2" />
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

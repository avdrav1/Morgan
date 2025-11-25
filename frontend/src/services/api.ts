import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: `${API_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Auth
export const authAPI = {
  register: (email: string, password: string, full_name?: string) =>
    api.post('/auth/register', { email, password, full_name }),
  
  login: (username: string, password: string) =>
    api.post('/auth/login', new URLSearchParams({ username, password }), {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    }),
  
  getCurrentUser: () => api.get('/auth/me'),
};

// Users
export const usersAPI = {
  getProfile: () => api.get('/users/me'),
  updateProfile: (data: any) => api.patch('/users/me', data),
  deleteAccount: () => api.delete('/users/me'),
  getAvailability: () => api.get('/users/me/availability'),
  updateAvailability: (windows: any[]) => api.put('/users/me/availability', { windows }),
  updateQuietHours: (quiet_hours_start: string, quiet_hours_end: string) =>
    api.put('/users/me/quiet-hours', { quiet_hours_start, quiet_hours_end }),
  updateTone: (preferred_tone: string) => api.put('/users/me/tone', { preferred_tone }),
  updateSystemPrompt: (custom_system_prompt: string) =>
    api.put('/users/me/system-prompt', { custom_system_prompt }),
  pauseMessaging: () => api.post('/users/me/pause-messaging'),
  resumeMessaging: () => api.post('/users/me/resume-messaging'),
  exportData: () => api.get('/users/me/export'),
};

// Projects
export const projectsAPI = {
  list: () => api.get('/projects/'),
  get: (id: string) => api.get(`/projects/${id}`),
  create: (data: any) => api.post('/projects/', data),
  update: (id: string, data: any) => api.patch(`/projects/${id}`, data),
  delete: (id: string) => api.delete(`/projects/${id}`),
  decompose: (id: string) => api.post(`/projects/${id}/decompose`),
  clarify: (id: string, answers: Record<string, string>) =>
    api.post(`/projects/${id}/clarify`, { answers }),
  approveTimeline: (id: string, approved: boolean, modifications: any[]) =>
    api.put(`/projects/${id}/timeline`, { approved, modifications }),
  pause: (id: string) => api.post(`/projects/${id}/pause`),
  archive: (id: string) => api.post(`/projects/${id}/archive`),
};

// Tasks
export const tasksAPI = {
  get: (id: string) => api.get(`/tasks/${id}`),
  create: (data: any) => api.post('/tasks/', data),
  update: (id: string, data: any) => api.patch(`/tasks/${id}`, data),
  complete: (id: string, notes?: string) =>
    api.post(`/tasks/${id}/complete`, { notes }),
  reschedule: (id: string, new_due_date: string, reason: string) =>
    api.post(`/tasks/${id}/reschedule`, { new_due_date, reason }),
  delete: (id: string) => api.delete(`/tasks/${id}`),
  getCheckIns: (id: string) => api.get(`/tasks/${id}/check-ins`),
};

// Check-ins
export const checkInsAPI = {
  respond: (id: string, response: string) =>
    api.post(`/check-ins/${id}/respond`, { response }),
  reschedule: (id: string, new_due_date: string, reason: string) =>
    api.post(`/check-ins/${id}/reschedule`, { new_due_date, reason }),
};

export default api;

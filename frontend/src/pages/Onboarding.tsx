import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { usersAPI, projectsAPI } from '../services/api';
import { CheckCircle, Clock, Calendar, Moon, MessageCircle, AlertCircle } from 'lucide-react';

type OnboardingStep = 'welcome' | 'tone' | 'availability' | 'complete';
type OnboardingMethod = 'dm' | 'web' | null;

interface AvailabilityWindow {
  day_of_week: number;
  start_time: string;
  end_time: string;
}

const TONE_OPTIONS = [
  {
    value: 'coach',
    label: 'Coach',
    description: 'Supportive, encouraging, and growth-focused. Perfect for building confidence.',
    icon: '🎯',
  },
  {
    value: 'manager',
    label: 'Manager',
    description: 'Professional, organized, and results-oriented. Keeps you on track efficiently.',
    icon: '📊',
  },
  {
    value: 'buddy',
    label: 'Accountability Buddy',
    description: 'Friendly, peer-like, and motivational. Like a supportive friend.',
    icon: '🤝',
  },
  {
    value: 'drill_sergeant',
    label: 'Drill Sergeant',
    description: 'Direct, demanding, and no-nonsense. Pushes you hard when you need it.',
    icon: '⚡',
  },
];

const DAYS_OF_WEEK = [
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
  'Sunday',
];

export default function Onboarding() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [onboardingMethod, setOnboardingMethod] = useState<OnboardingMethod>(null);
  const [step, setStep] = useState<OnboardingStep>('welcome');
  const [selectedTone, setSelectedTone] = useState<string>('coach');
  const [quietHoursStart, setQuietHoursStart] = useState<string>('22:00');
  const [quietHoursEnd, setQuietHoursEnd] = useState<string>('08:00');
  const [availabilityWindows, setAvailabilityWindows] = useState<AvailabilityWindow[]>([
    { day_of_week: 1, start_time: '09:00', end_time: '17:00' },
    { day_of_week: 2, start_time: '09:00', end_time: '17:00' },
    { day_of_week: 3, start_time: '09:00', end_time: '17:00' },
    { day_of_week: 4, start_time: '09:00', end_time: '17:00' },
    { day_of_week: 5, start_time: '09:00', end_time: '17:00' },
  ]);

  // Detect onboarding method from URL parameters
  useEffect(() => {
    const method = searchParams.get('method') as OnboardingMethod;
    const reason = searchParams.get('reason');
    
    if (method === 'dm') {
      setOnboardingMethod('dm');
    } else if (method === 'web' || reason === 'dm_failed') {
      setOnboardingMethod('web');
    } else {
      // Default to web onboarding if no method specified
      setOnboardingMethod('web');
    }
  }, [searchParams]);

  const updateToneMutation = useMutation({
    mutationFn: (tone: string) => usersAPI.updateTone(tone),
  });

  const updateAvailabilityMutation = useMutation({
    mutationFn: (windows: AvailabilityWindow[]) => usersAPI.updateAvailability(windows),
  });

  const updateQuietHoursMutation = useMutation({
    mutationFn: ({ start, end }: { start: string; end: string }) =>
      usersAPI.updateQuietHours(start, end),
  });

  const handleNext = async () => {
    if (step === 'welcome') {
      setStep('tone');
    } else if (step === 'tone') {
      await updateToneMutation.mutateAsync(selectedTone);
      setStep('availability');
    } else if (step === 'availability') {
      await updateAvailabilityMutation.mutateAsync(availabilityWindows);
      await updateQuietHoursMutation.mutateAsync({
        start: quietHoursStart,
        end: quietHoursEnd,
      });
      setStep('complete');
    } else if (step === 'complete') {
      navigate('/');
    }
  };

  const handleSkip = () => {
    navigate('/');
  };

  const toggleDay = (dayIndex: number) => {
    const existingWindow = availabilityWindows.find((w) => w.day_of_week === dayIndex);
    
    if (existingWindow) {
      setAvailabilityWindows(availabilityWindows.filter((w) => w.day_of_week !== dayIndex));
    } else {
      setAvailabilityWindows([
        ...availabilityWindows,
        { day_of_week: dayIndex, start_time: '09:00', end_time: '17:00' },
      ]);
    }
  };

  const updateWindowTime = (dayIndex: number, field: 'start_time' | 'end_time', value: string) => {
    setAvailabilityWindows(
      availabilityWindows.map((w) =>
        w.day_of_week === dayIndex ? { ...w, [field]: value } : w
      )
    );
  };

  // Show loading state while determining onboarding method
  if (onboardingMethod === null) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  // Show "Check Discord DMs" message if DM onboarding is active
  if (onboardingMethod === 'dm') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center py-12 px-4">
        <div className="max-w-2xl w-full">
          <div className="bg-white rounded-2xl shadow-xl p-8 text-center">
            <div className="w-20 h-20 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-6">
              <MessageCircle className="w-12 h-12 text-blue-600" />
            </div>
            
            <h1 className="text-3xl font-bold text-gray-900 mb-4">
              Check Your Discord DMs!
            </h1>
            
            <p className="text-lg text-gray-600 mb-6">
              We've sent you a direct message on Discord to complete your onboarding.
            </p>
            
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-6">
              <h3 className="font-semibold text-gray-900 mb-3">What to expect:</h3>
              <ul className="text-left text-gray-700 space-y-2">
                <li className="flex items-start">
                  <CheckCircle className="w-5 h-5 text-blue-600 mr-2 mt-0.5 flex-shrink-0" />
                  <span>A friendly welcome message from our bot</span>
                </li>
                <li className="flex items-start">
                  <CheckCircle className="w-5 h-5 text-blue-600 mr-2 mt-0.5 flex-shrink-0" />
                  <span>A few simple questions about your project</span>
                </li>
                <li className="flex items-start">
                  <CheckCircle className="w-5 h-5 text-blue-600 mr-2 mt-0.5 flex-shrink-0" />
                  <span>Your preferences for check-ins and communication style</span>
                </li>
              </ul>
            </div>
            
            <p className="text-sm text-gray-500 mb-6">
              The whole process takes just a few minutes and happens right in Discord!
            </p>
            
            <div className="border-t border-gray-200 pt-6">
              <p className="text-sm text-gray-600 mb-4">
                Having trouble? You can complete onboarding here instead.
              </p>
              <button
                onClick={() => setOnboardingMethod('web')}
                className="text-blue-600 hover:text-blue-700 font-medium"
              >
                Use Web Onboarding Instead →
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Show web onboarding form (existing flow)
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center py-12 px-4">
      <div className="max-w-4xl w-full">
        {/* Show DM failure notice if applicable */}
        {searchParams.get('reason') === 'dm_failed' && (
          <div className="mb-6 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <div className="flex items-start">
              <AlertCircle className="w-5 h-5 text-yellow-600 mr-3 mt-0.5 flex-shrink-0" />
              <div>
                <h3 className="font-semibold text-yellow-900 mb-1">
                  Discord DMs Not Available
                </h3>
                <p className="text-sm text-yellow-800">
                  We couldn't send you a Discord DM. This might be because you have DMs disabled 
                  from server members. No worries - you can complete onboarding here!
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Progress indicator */}
        <div className="mb-8">
          <div className="flex items-center justify-center space-x-4">
            {['welcome', 'tone', 'availability', 'complete'].map((s, idx) => (
              <React.Fragment key={s}>
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center ${
                    step === s
                      ? 'bg-blue-600 text-white'
                      : ['welcome', 'tone', 'availability', 'complete'].indexOf(step) >
                        ['welcome', 'tone', 'availability', 'complete'].indexOf(s)
                      ? 'bg-green-500 text-white'
                      : 'bg-gray-300 text-gray-600'
                  }`}
                >
                  {['welcome', 'tone', 'availability', 'complete'].indexOf(step) >
                  ['welcome', 'tone', 'availability', 'complete'].indexOf(s) ? (
                    <CheckCircle className="w-6 h-6" />
                  ) : (
                    idx + 1
                  )}
                </div>
                {idx < 3 && (
                  <div
                    className={`h-1 w-16 ${
                      ['welcome', 'tone', 'availability', 'complete'].indexOf(step) > idx
                        ? 'bg-green-500'
                        : 'bg-gray-300'
                    }`}
                  />
                )}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="bg-white rounded-2xl shadow-xl p-8">
          {step === 'welcome' && (
            <div className="text-center">
              <h1 className="text-4xl font-bold text-gray-900 mb-4">
                Welcome to Your Accountability Assistant
              </h1>
              <p className="text-xl text-gray-600 mb-8">
                I'm here to help you turn your goals into reality through proactive check-ins,
                personalized coaching, and adaptive support.
              </p>
              
              <div className="grid md:grid-cols-3 gap-6 mb-8">
                <div className="p-6 bg-blue-50 rounded-lg">
                  <div className="text-4xl mb-3">🎯</div>
                  <h3 className="font-semibold text-gray-900 mb-2">Break Down Goals</h3>
                  <p className="text-sm text-gray-600">
                    Transform vague ideas into clear, actionable steps
                  </p>
                </div>
                
                <div className="p-6 bg-green-50 rounded-lg">
                  <div className="text-4xl mb-3">📅</div>
                  <h3 className="font-semibold text-gray-900 mb-2">Proactive Check-ins</h3>
                  <p className="text-sm text-gray-600">
                    Get timely reminders when you should be working
                  </p>
                </div>
                
                <div className="p-6 bg-purple-50 rounded-lg">
                  <div className="text-4xl mb-3">💪</div>
                  <h3 className="font-semibold text-gray-900 mb-2">Adaptive Coaching</h3>
                  <p className="text-sm text-gray-600">
                    Receive personalized support when you're stuck
                  </p>
                </div>
              </div>

              <p className="text-gray-600 mb-8">
                Let's take a few minutes to customize your experience.
              </p>
            </div>
          )}

          {step === 'tone' && (
            <div>
              <h2 className="text-3xl font-bold text-gray-900 mb-4">Choose Your Coaching Style</h2>
              <p className="text-gray-600 mb-8">
                How would you like me to communicate with you? You can change this anytime.
              </p>

              <div className="grid md:grid-cols-2 gap-4 mb-8">
                {TONE_OPTIONS.map((tone) => (
                  <button
                    key={tone.value}
                    onClick={() => setSelectedTone(tone.value)}
                    className={`p-6 rounded-lg border-2 text-left transition-all ${
                      selectedTone === tone.value
                        ? 'border-blue-600 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className="flex items-start space-x-4">
                      <div className="text-4xl">{tone.icon}</div>
                      <div className="flex-1">
                        <h3 className="font-semibold text-gray-900 mb-1">{tone.label}</h3>
                        <p className="text-sm text-gray-600">{tone.description}</p>
                      </div>
                      {selectedTone === tone.value && (
                        <CheckCircle className="w-6 h-6 text-blue-600" />
                      )}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {step === 'availability' && (
            <div>
              <h2 className="text-3xl font-bold text-gray-900 mb-4">Set Your Availability</h2>
              <p className="text-gray-600 mb-8">
                Tell me when you're available for check-ins. I'll never message you outside these times.
              </p>

              {/* Quiet Hours */}
              <div className="mb-8 p-6 bg-gray-50 rounded-lg">
                <div className="flex items-center mb-4">
                  <Moon className="w-5 h-5 text-gray-700 mr-2" />
                  <h3 className="font-semibold text-gray-900">Quiet Hours</h3>
                </div>
                <p className="text-sm text-gray-600 mb-4">
                  I won't send any messages during these hours.
                </p>
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Start Time
                    </label>
                    <input
                      type="time"
                      value={quietHoursStart}
                      onChange={(e) => setQuietHoursStart(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      End Time
                    </label>
                    <input
                      type="time"
                      value={quietHoursEnd}
                      onChange={(e) => setQuietHoursEnd(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </div>
              </div>

              {/* Availability Windows */}
              <div className="mb-8">
                <div className="flex items-center mb-4">
                  <Calendar className="w-5 h-5 text-gray-700 mr-2" />
                  <h3 className="font-semibold text-gray-900">Available Days & Times</h3>
                </div>
                <p className="text-sm text-gray-600 mb-4">
                  Select the days and times when you're typically available.
                </p>
                
                <div className="space-y-3">
                  {DAYS_OF_WEEK.map((day, idx) => {
                    const window = availabilityWindows.find((w) => w.day_of_week === idx);
                    const isSelected = !!window;

                    return (
                      <div
                        key={idx}
                        className={`p-4 rounded-lg border-2 transition-all ${
                          isSelected ? 'border-blue-600 bg-blue-50' : 'border-gray-200'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <button
                            onClick={() => toggleDay(idx)}
                            className="flex items-center space-x-3 flex-1"
                          >
                            <div
                              className={`w-6 h-6 rounded border-2 flex items-center justify-center ${
                                isSelected
                                  ? 'bg-blue-600 border-blue-600'
                                  : 'border-gray-300'
                              }`}
                            >
                              {isSelected && <CheckCircle className="w-4 h-4 text-white" />}
                            </div>
                            <span className="font-medium text-gray-900">{day}</span>
                          </button>

                          {isSelected && window && (
                            <div className="flex items-center space-x-2">
                              <Clock className="w-4 h-4 text-gray-500" />
                              <input
                                type="time"
                                value={window.start_time}
                                onChange={(e) =>
                                  updateWindowTime(idx, 'start_time', e.target.value)
                                }
                                className="px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                              />
                              <span className="text-gray-500">to</span>
                              <input
                                type="time"
                                value={window.end_time}
                                onChange={(e) =>
                                  updateWindowTime(idx, 'end_time', e.target.value)
                                }
                                className="px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                              />
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {step === 'complete' && (
            <div className="text-center">
              <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
                <CheckCircle className="w-12 h-12 text-green-600" />
              </div>
              <h2 className="text-3xl font-bold text-gray-900 mb-4">You're All Set!</h2>
              <p className="text-xl text-gray-600 mb-8">
                Your accountability assistant is ready to help you achieve your goals.
              </p>
              <p className="text-gray-600 mb-8">
                Let's create your first project and start making progress!
              </p>
            </div>
          )}

          {/* Navigation buttons */}
          <div className="flex justify-between items-center mt-8 pt-6 border-t border-gray-200">
            <button
              onClick={handleSkip}
              className="px-6 py-2 text-gray-600 hover:text-gray-800 transition-colors"
            >
              Skip for now
            </button>
            <button
              onClick={handleNext}
              disabled={
                updateToneMutation.isPending ||
                updateAvailabilityMutation.isPending ||
                updateQuietHoursMutation.isPending
              }
              className="px-8 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {step === 'complete'
                ? 'Get Started'
                : updateToneMutation.isPending ||
                  updateAvailabilityMutation.isPending ||
                  updateQuietHoursMutation.isPending
                ? 'Saving...'
                : 'Continue'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

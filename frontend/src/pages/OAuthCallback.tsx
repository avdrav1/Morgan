import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

export default function OAuthCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  
  useEffect(() => {
    const token = searchParams.get('token');
    const newUser = searchParams.get('new_user') === 'true';
    const dmOnboarding = searchParams.get('dm_onboarding') === 'true';
    const error = searchParams.get('error');
    
    if (error) {
      console.error('OAuth error:', error);
      navigate('/login?error=' + error);
      return;
    }
    
    if (token) {
      // Store the token
      localStorage.setItem('token', token);
      
      // Redirect based on whether user is new and onboarding method
      // Use window.location to force a full page reload so AuthContext picks up the token
      if (newUser) {
        if (dmOnboarding) {
          // DM onboarding is active - show "Check Discord DMs" message
          window.location.href = '/onboarding?method=dm';
        } else {
          // DM onboarding failed - show web onboarding form
          window.location.href = '/onboarding?method=web';
        }
      } else {
        window.location.href = '/';
      }
    } else {
      navigate('/login?error=no_token');
    }
  }, [searchParams, navigate]);
  
  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
        <p className="mt-4 text-gray-600">Completing sign in...</p>
      </div>
    </div>
  );
}

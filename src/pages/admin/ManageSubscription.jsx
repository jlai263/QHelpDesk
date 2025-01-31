import React, { useState, useEffect } from 'react';
import { toast } from 'react-toastify';

const ManageSubscription = () => {
  const [subscription, setSubscription] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Fetch subscription data on component mount
  useEffect(() => {
    const fetchSubscription = async () => {
      try {
        const response = await fetch('/api/subscription', {
          headers: { 'Content-Type': 'application/json' }
        });
        if (!response.ok) {
          throw new Error('Failed to fetch subscription details');
        }
        const data = await response.json();
        setSubscription(data.subscription);
      } catch (err) {
        setError('Failed to load subscription details');
        console.error('Error fetching subscription:', err);
        toast.error('Failed to load subscription details');
      }
    };

    fetchSubscription();
  }, []);

  const handleCancel = async () => {
    if (!window.confirm('Are you sure you want to cancel your subscription? You will still have access until the end of your current billing period.')) {
      return;
    }

    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/subscription/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Failed to cancel subscription');
      }
      
      const data = await response.json();
      setSubscription(data.subscription);
      toast.success('Subscription successfully cancelled');
    } catch (err) {
      setError('Failed to cancel subscription');
      console.error('Error canceling subscription:', err);
      toast.error(err.message || 'Failed to cancel subscription');
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (timestamp) => {
    return new Date(timestamp * 1000).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  if (error) {
    return (
      <div className="max-w-3xl mx-auto p-6">
        <div className="bg-red-50 border border-red-200 text-red-600 rounded-md p-4">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto p-6">
      <h2 className="text-2xl font-bold mb-6">Current Subscription</h2>
      
      {subscription ? (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="mb-4">
            <h3 className="text-xl font-semibold mb-2">Professional Plan</h3>
            <p className="text-gray-600">
              {subscription.plan?.description || 'Enterprise-grade features and support'}
            </p>
          </div>

          {subscription.status === 'active' && !subscription.cancel_at_period_end && (
            <button
              onClick={handleCancel}
              disabled={loading}
              className="bg-red-600 hover:bg-red-700 text-white font-semibold py-2 px-4 rounded disabled:opacity-50 transition-colors duration-200"
            >
              {loading ? 'Canceling...' : 'Cancel Subscription'}
            </button>
          )}

          {subscription.cancel_at_period_end && (
            <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-md">
              <p className="text-yellow-800">
                Your subscription will end on {formatDate(subscription.current_period_end)}
              </p>
              <p className="text-sm text-yellow-600 mt-2">
                You will continue to have access to all features until this date.
              </p>
            </div>
          )}

          {subscription.status === 'canceled' && (
            <div className="mt-4 p-4 bg-gray-50 border border-gray-200 rounded-md">
              <p className="text-gray-800">
                Your subscription is canceled.
              </p>
              <p className="text-sm text-gray-600 mt-2">
                You can resubscribe at any time to restore access.
              </p>
            </div>
          )}
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="animate-pulse flex space-x-4">
            <div className="flex-1 space-y-4 py-1">
              <div className="h-4 bg-gray-200 rounded w-3/4"></div>
              <div className="space-y-2">
                <div className="h-4 bg-gray-200 rounded"></div>
                <div className="h-4 bg-gray-200 rounded w-5/6"></div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ManageSubscription; 
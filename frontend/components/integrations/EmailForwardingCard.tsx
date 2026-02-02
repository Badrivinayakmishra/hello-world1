'use client';

import { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:5003';

interface EmailForwardingStatus {
  success: boolean;
  forwarding_address: string;
  configured: boolean;
  instructions: string;
}

export default function EmailForwardingCard() {
  const [status, setStatus] = useState<EmailForwardingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetching, setFetching] = useState(false);
  const [result, setResult] = useState<any>(null);

  useEffect(() => {
    fetchStatus();
  }, []);

  const fetchStatus = async () => {
    try {
      // Use public endpoint (no auth required)
      const response = await axios.get(`${API_BASE_URL}/api/email-forwarding/status-public`);
      setStatus(response.data);
    } catch (error) {
      console.error('Failed to fetch status:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFetchEmails = async () => {
    setFetching(true);
    setResult(null);

    try {
      // Use public endpoint (no auth required)
      const response = await axios.post(`${API_BASE_URL}/api/email-forwarding/fetch-public`, {});

      setResult(response.data);
    } catch (error: any) {
      setResult({
        success: false,
        error: error.response?.data?.error || error.message
      });
    } finally {
      setFetching(false);
    }
  };

  // Clean black and white design to match site aesthetic
  return (
    <div className="bg-white p-6">
      {/* Instructions */}
      <div className="mb-6">
        <p className="text-sm text-gray-600 mb-3" style={{ fontFamily: 'Inter, sans-serif' }}>
          Forward emails to this address to add them to your knowledge base:
        </p>
        <div className="border border-gray-300 rounded-lg px-4 py-3 bg-gray-50">
          <code className="text-base font-mono text-gray-900">beatatucla@gmail.com</code>
        </div>
      </div>

      {/* Fetch Button */}
      <button
        onClick={handleFetchEmails}
        disabled={fetching}
        className={`w-full py-3 px-4 rounded-lg font-medium text-sm transition-all ${
          fetching
            ? 'bg-gray-100 text-gray-400 cursor-wait border border-gray-300'
            : 'bg-black text-white hover:bg-gray-800 border border-black'
        }`}
        style={{ fontFamily: 'Inter, sans-serif' }}
      >
        {fetching ? 'Fetching emails...' : 'Fetch Emails'}
      </button>

      {/* Result */}
      {result && (
        <div className={`mt-4 p-4 rounded-lg border ${
          result.success
            ? 'bg-green-50 border-green-200'
            : 'bg-red-50 border-red-200'
        }`}>
          {result.success ? (
            <div>
              <p className="text-sm font-medium text-green-900 mb-1" style={{ fontFamily: 'Inter, sans-serif' }}>
                ✓ Success
              </p>
              <p className="text-sm text-green-700" style={{ fontFamily: 'Inter, sans-serif' }}>
                {result.processed} emails fetched
                {result.message && ` - ${result.message}`}
              </p>
              {result.emails && result.emails.length > 0 && (
                <div className="mt-3 space-y-2">
                  {result.emails.slice(0, 3).map((email: any, idx: number) => (
                    <div key={idx} className="text-xs text-gray-600 border-l-2 border-green-300 pl-3 py-1">
                      <p className="font-medium text-gray-900" style={{ fontFamily: 'Inter, sans-serif' }}>
                        {email.subject}
                      </p>
                      <p className="text-gray-500" style={{ fontFamily: 'Inter, sans-serif' }}>
                        {email.from}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div>
              <p className="text-sm font-medium text-red-900 mb-1" style={{ fontFamily: 'Inter, sans-serif' }}>
                ✗ Error
              </p>
              <p className="text-sm text-red-700" style={{ fontFamily: 'Inter, sans-serif' }}>
                {result.error || 'Failed to fetch emails'}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

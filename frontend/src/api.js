/**
 * api.js
 * All API calls to the MindMint backend.
 * Set VITE_API_URL in .env to point at your Render service URL in production.
 *
 * Financial values from the backend are stored as integer microunits
 * (1 USDC = 1_000_000 microunits). The microunitsToUsdc helper converts
 * them to floats here, at the API boundary, so components always receive
 * plain USDC floats and never need to know about microunits.
 */

import axios from 'axios';

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8080';
const API_KEY = import.meta.env.VITE_API_KEY || '';

const api = axios.create({ baseURL: BASE, timeout: 90_000 });

api.interceptors.response.use(
  response => response,
  error => {
    if (!error.response) {
      console.error('[API] Network error — is the backend running?');
    } else if (error.response.status >= 500) {
      console.error('[API] Server error', error.response.status, error.response.data);
    } else if (error.response.status === 401) {
      console.error('[API] Unauthorized — check VITE_API_KEY in .env');
    }
    return Promise.reject(error);
  }
);

const microunitsToUsdc = (v) => (v ?? 0) / 1_000_000;


export const getMarketplace = (sort = 'top_rated', limit = 20, offset = 0) =>
  api.get('/dashboard/marketplace', { params: { sort, limit, offset } })
     .then(r => r.data.listings.map(b => ({
       ...b,
       price_usdc: microunitsToUsdc(b.price_microunits),
     })));

export const getPlatformStats = () =>
  api.get('/dashboard/platform').then(r => {
    const d = r.data;
    return {
      ...d,
      total_volume_usdc: microunitsToUsdc(d.total_volume_microunits),
      platform_earned_usdc: microunitsToUsdc(d.platform_earned_microunits),
    };
  });

export const getLeaderboard = (limit = 10) =>
  api.get('/dashboard/leaderboard', { params: { limit } })
     .then(r => r.data.leaderboard.map(e => ({
       ...e,
       total_earned_usdc: microunitsToUsdc(e.total_earned_microunits),
     })));

export const searchMemories = (q, top_k = 5) =>
  api.get('/memory/search', { params: { q, top_k } })
     .then(r => r.data.results);

export const getPublisherDashboard = (wallet) =>
  api.get(`/dashboard/publisher/${wallet}`).then(r => {
    const d = r.data;
    return {
      ...d,
      total_earned_usdc: microunitsToUsdc(d.total_earned_microunits),
      top_bundles: (d.top_bundles || []).map(b => ({
        ...b,
        total_earned_usdc: microunitsToUsdc(b.total_earned_microunits),
      })),
      recent_payments: (d.recent_payments || []).map(p => ({
        ...p,
        gross_usdc: microunitsToUsdc(p.gross_microunits),
        publisher_earned_usdc: microunitsToUsdc(p.publisher_earned_microunits),
      })),
    };
  });

export const rateBundleApi = (bundleId, rating, wallet) =>
  api.post(`/dashboard/rate/${bundleId}`, {
    rating,
    consumer_wallet: wallet,
  }).then(r => r.data);


export const runConsumerAgent = (task, maxBudget = 0.01) =>
  api.post(
    '/agent/consumer/run',
    { task, max_budget_usdc: maxBudget },
    { headers: { 'X-API-Key': API_KEY } }
  ).then(r => {
    const d = r.data;
    return {
      ...d,
      total_spent_usdc: microunitsToUsdc(d.total_spent_microunits),
      bundles_purchased: (d.bundles_purchased || []).map(b => ({
        ...b,
        amount_usdc: microunitsToUsdc(b.amount_microunits),
      })),
    };
  });


export const publishBundle = (payload) =>
  api.post('/memory/publish', payload).then(r => r.data);

export const getHealth = () =>
  api.get('/health').then(r => r.data);
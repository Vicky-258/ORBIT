/**
 * Context gathering & Requirement interview engine for ORBIT
 * Determines whether the user's application description has sufficient
 * architectural clarity, or if focused technical follow-ups are needed first.
 */

export function analyzeRequirementsCompleteness(prompt, history = []) {
  if (!prompt || typeof prompt !== 'string') return { isComplete: false, questions: [] };

  const fullContext = [...history.map(m => m.content || ''), prompt].join(' ').toLowerCase();

  // Detect domain traits
  const isMediaSharing = /photo|image|video|media|stream|picture|gallery/i.test(fullContext);
  const isSocialCommunity = /friend|feed|social|post|follow|like|comment/i.test(fullContext);
  const isEcommerceBooking = /hotel|book|order|cart|checkout|store|commerce|payment/i.test(fullContext);
  const isTelemetryRealtime = /drone|tracking|fleet|sensor|iot|game|matchmaking|real-?time|telemetry/i.test(fullContext);

  // Missing criteria detection
  const hasMediaHandling = /thumbnail|resolution|transcod|compress|s3|cdn|bucket|blob|video/i.test(fullContext);
  const hasAccessPattern = /feed|timeline|public|private|direct|both/i.test(fullContext);
  const hasInteractions = /like|comment|notification|push|follow|reaction/i.test(fullContext);
  const hasScaleClarified = /initial|target|peak|future|launch|burst|rps|qps/i.test(fullContext);
  const hasDataConsistency = /acid|eventual|strict|real-?time/i.test(fullContext);

  const missingAspects = [];

  if (isMediaSharing || isSocialCommunity) {
    if (!hasMediaHandling) {
      missingAspects.push({
        id: 'media_processing',
        question: 'Are uploads strictly photos, or also video clips? And will they need on-the-fly thumbnail generation or multiple resolutions?',
        options: [
          'Photos only with automatic thumbnails & mobile variants',
          'Photos and short video clips (< 60s)',
          'Raw photo storage without processing'
        ]
      });
    }

    if (!hasAccessPattern) {
      missingAspects.push({
        id: 'feed_visibility',
        question: 'How should photos be distributed — through a global public feed, private friends-only timelines, or both?',
        options: [
          'Hybrid: Public discovery feed + friends timeline',
          'Friends-only private timeline (fan-out on write)',
          'Purely public discovery feed'
        ]
      });
    }

    if (!hasInteractions) {
      missingAspects.push({
        id: 'social_features',
        question: 'Will users interact with posts via likes, comments, and real-time push notifications?',
        options: [
          'Yes: Likes, nested comments & push notifications',
          'Read/view only at launch, social interactions later',
          'Likes & saves only (no comments)'
        ]
      });
    }

    if (!hasScaleClarified) {
      missingAspects.push({
        id: 'scale_timeline',
        question: 'Is 100K active users your initial launch day expectation or a 6-12 month growth milestone?',
        options: [
          'Day-1 launch expectation (must size for peak now)',
          'Target growth within 6-12 months (start cost-effective)',
          'Prototype phase (< 5K DAU first)'
        ]
      });
    }
  } else if (isEcommerceBooking) {
    if (!hasDataConsistency) {
      missingAspects.push({
        id: 'inventory_consistency',
        question: 'How critical is strict zero-overbooking ACID consistency vs high availability browsing?',
        options: [
          'Strict ACID transactions for booking (PostgreSQL / 2PC)',
          'Eventual consistency with reservation locks',
          'Read-heavy cache with optimistic locking'
        ]
      });
    }
  } else if (isTelemetryRealtime) {
    if (!hasScaleClarified) {
      missingAspects.push({
        id: 'telemetry_frequency',
        question: 'What is the expected ping frequency per device/client (e.g. 1Hz, 10Hz)?',
        options: [
          'High frequency: 1-5 updates per second per device',
          'Moderate: 1 update every 10-30 seconds',
          'Event-driven / on status change only'
        ]
      });
    }
  }

  // Count user turns in this conversation so far
  const userTurns = history.filter(m => m.sender === 'user').length;

  // We ask 1 focused clarification turn to gather key requirements, then synthesize
  const hasGatheredSufficientContext = userTurns >= 1 || missingAspects.length === 0 || (fullContext.length > 350 && hasScaleClarified);

  return {
    isComplete: hasGatheredSufficientContext,
    nextClarification: missingAspects[0] || null,
    remainingClarifications: missingAspects.slice(1),
  };
}

/**
 * Workload Inference Engine for ORBIT Architecture Copilot
 *
 * Automatically translates natural-language project descriptions, user scale,
 * and app domain into concrete, calibrated system engineering parameters
 * (RPS, Latency SLA, Read/Write ratio, and Cloud Budget) with human explanations.
 */

export function inferWorkloadFromPrompt(promptText) {
  if (!promptText || typeof promptText !== 'string') {
    return null;
  }

  const text = promptText.toLowerCase().trim();
  if (text.length < 5) return null;

  const result = {
    detectedDomain: 'general',
    domainLabel: 'General Web Application',
    domainDescription: 'Standard interactive web application with balanced caching needs',
    qps: 300,
    p95_sla_ms: 100,
    read_ratio: 0.90,
    write_ratio: 0.10,
    budget_usd: 250,
    explanations: {
      qps: 'Estimated baseline load for early production services',
      p95_sla_ms: 'Standard web application p95 latency ceiling (< 100 ms)',
      read_ratio: 'Standard read-heavy access pattern (90% reads, 10% writes)',
      budget_usd: 'Standard lean cloud infrastructure allocation ($250/mo)',
    },
    humanGuide: {
      qps: 'How busy your backend is at peak times',
      p95_sla_ms: 'How fast 95% of requests must complete',
      read_ratio: 'Whether users mostly browse content or submit new data',
      budget_usd: 'Target monthly spend for database and compute servers',
    },
    inferredDetails: [],
    confidence: 'inferred',
  };

  // 1. Infer Throughput (RPS) from explicit RPS, DAU, or User Count
  const rpsMatch = text.match(/(\d+(?:\.\d+)?)\s*(?:rps|req\/s|requests?\s*(?:per|\/)\s*sec|qps)/i);
  const dauMatch = text.match(/(\d+(?:\.\d+)?)\s*(k|thousand|m|million)?\s*(?:active\s*)?(?:daily\s*)?(?:users|dau|mau|people|clients|followers|subscribers|devices)/i);

  if (rpsMatch) {
    const rawRps = parseFloat(rpsMatch[1]);
    result.qps = Math.min(5000, Math.max(10, Math.round(rawRps)));
    result.explanations.qps = `Target load explicitly specified in prompt (${result.qps} req/s)`;
    result.inferredDetails.push(`Explicit throughput: ${result.qps} requests/sec`);
  } else if (dauMatch) {
    const num = parseFloat(dauMatch[1]);
    const multiplier = dauMatch[2]?.startsWith('m') ? 1_000_000 : dauMatch[2] ? 1_000 : 1;
    const totalUsers = num * multiplier;

    // Rule of thumb: ~60 user actions/day over 14 peak hours with 2x burst multiplier
    const calculatedRps = Math.round((totalUsers * 60) / (14 * 3600) * 2.0);
    result.qps = Math.min(5000, Math.max(25, calculatedRps));
    const userDisplay = totalUsers >= 1_000_000 ? `${(totalUsers / 1_000_000).toFixed(1)}M` : `${Math.round(totalUsers / 1000)}K`;
    result.explanations.qps = `Calculated ~${result.qps} peak requests/sec from ${userDisplay} active daily users (assuming ~60 interactions/user/day with peak burst factor)`;
    result.inferredDetails.push(`${userDisplay} Daily Active Users ➔ ~${result.qps} peak req/s`);
  }

  // 2. Infer Domain & Access Pattern (Read/Write Ratio)
  const isSocialOrPhoto = /photo|image|instagram|social|feed|share|follow|like|comment|stream|media|browse|catalog|post|article|blog|video/i.test(text);
  const isFinancial = /transaction|bank|payment|crypto|wallet|ledger|trading|checkout|order|finance|money|transfer/i.test(text);
  const isChat = /chat|messaging|messenger|conversation|real-time|websocket/i.test(text);
  const isTelemetry = /telemetry|iot|sensor|event|tracking|analytics|log|metrics|ingest|queue|monitoring/i.test(text);

  if (isSocialOrPhoto) {
    result.detectedDomain = 'social_photo';
    result.domainLabel = 'Photo Sharing & Social Feed';
    result.domainDescription = 'Read-dominated workload where users browse feeds and media 10x more than they post';
    result.read_ratio = 0.90;
    result.write_ratio = 0.10;
    result.p95_sla_ms = 100;
    result.explanations.read_ratio = 'Social & photo feeds are 90% Read (users view feeds, comments, and images continuously vs. posting occasionally)';
    result.explanations.p95_sla_ms = 'Snappy mobile feed scrolling requires < 100ms response times to prevent loading spinners';
    result.inferredDetails.push('Social & Media pattern: 90% view traffic / 10% upload traffic');
  } else if (isFinancial) {
    result.detectedDomain = 'financial_oltp';
    result.domainLabel = 'Financial & Transactional OLTP';
    result.domainDescription = 'High-integrity ledger where writes require ACID transactional guarantees';
    result.read_ratio = 0.40;
    result.write_ratio = 0.60;
    result.p95_sla_ms = 150;
    result.explanations.read_ratio = 'Financial platforms have a balanced 40% Read / 60% Write profile due to frequent ledger updates and balance mutations';
    result.explanations.p95_sla_ms = 'ACID transactional locking safely operates under 150ms p95 latency';
    result.inferredDetails.push('Transactional OLTP pattern: 40% balance queries / 60% ledger updates');
  } else if (isChat) {
    result.detectedDomain = 'chat_messaging';
    result.domainLabel = 'Chat & Real-time Messaging';
    result.domainDescription = 'Balanced messaging workload with high-concurrency read and write operations';
    result.read_ratio = 0.50;
    result.write_ratio = 0.50;
    result.p95_sla_ms = 80;
    result.explanations.read_ratio = 'Chat involves balanced 50% Read / 50% Write (reading incoming messages and sending replies at equal rates)';
    result.explanations.p95_sla_ms = 'Real-time messaging targets < 80ms latency for seamless conversation flow';
    result.inferredDetails.push('Chat & Messaging pattern: 50% read message / 50% send message');
  } else if (isTelemetry) {
    result.detectedDomain = 'telemetry_ingest';
    result.domainLabel = 'Event Ingestion & Telemetry';
    result.domainDescription = 'Write-dominated pipeline capturing telemetry data continuously';
    result.read_ratio = 0.10;
    result.write_ratio = 0.90;
    result.p95_sla_ms = 100;
    result.explanations.read_ratio = 'Telemetry is 90% Write (continuous metric bursts with periodic read querying)';
    result.explanations.p95_sla_ms = 'Fast message enqueue SLA (< 100ms) with background database persistence';
    result.inferredDetails.push('Telemetry & Ingestion pattern: 10% dashboard reads / 90% event writes');
  }

  // Check for explicit ratio override (e.g., "95% reads", "80% read")
  const explicitReadMatch = text.match(/(\d+)\s*%\s*reads?/i);
  if (explicitReadMatch) {
    const rPct = Math.min(99, Math.max(1, parseInt(explicitReadMatch[1])));
    result.read_ratio = parseFloat((rPct / 100).toFixed(2));
    result.write_ratio = parseFloat((1 - result.read_ratio).toFixed(2));
    result.explanations.read_ratio = `Traffic split explicitly defined in prompt (${rPct}% Read / ${100 - rPct}% Write)`;
    result.inferredDetails.push(`Explicit split: ${rPct}% Read / ${100 - rPct}% Write`);
  }

  // 3. Infer Latency SLA if explicit
  const explicitSlaMatch = text.match(/(?:p95|latency|sla|response\s*time)?\s*(?:under|<=|<|below|of)?\s*(\d+)\s*ms/i);
  if (explicitSlaMatch) {
    result.p95_sla_ms = parseInt(explicitSlaMatch[1]);
    result.explanations.p95_sla_ms = `Latency SLA ceiling explicitly specified in prompt (< ${result.p95_sla_ms} ms p95)`;
    result.inferredDetails.push(`Explicit SLA: < ${result.p95_sla_ms} ms`);
  }

  // 4. Infer Monthly Budget based on Throughput and User Scale
  const explicitBudgetMatch = text.match(/(?:\$|usd\s*)(\d+)/i) || text.match(/(\d+)\s*(?:dollars?|usd|\/mo)/i);
  if (explicitBudgetMatch) {
    result.budget_usd = parseInt(explicitBudgetMatch[1]);
    result.explanations.budget_usd = `Monthly infrastructure budget explicitly specified in prompt ($${result.budget_usd}/mo)`;
    result.inferredDetails.push(`Explicit budget: $${result.budget_usd}/month`);
  } else {
    if (result.qps <= 150) {
      result.budget_usd = 150;
      result.explanations.budget_usd = 'Estimated $150/mo for a dedicated single-instance database cluster';
    } else if (result.qps <= 500) {
      result.budget_usd = 250;
      result.explanations.budget_usd = 'Estimated $250/mo for managed caching layer + primary PostgreSQL database';
    } else {
      result.budget_usd = 450;
      result.explanations.budget_usd = 'Estimated $450/mo for high-traffic multi-node distributed infrastructure';
    }
  }

  return result;
}

export function enrichPromptWithTechnicalEstimates(conversationContext) {
  if (!conversationContext || typeof conversationContext !== 'string') {
    return conversationContext;
  }

  const text = conversationContext.toLowerCase();
  const additions = [];

  const hasExplicitRps = /(\d+)\s*(?:rps|req\/s|qps)/i.test(text);
  const hasExplicitP95 = /(\d+)\s*ms/i.test(text);
  const hasExplicitBudget = /\$\s*(\d+)/i.test(text);

  const userMatch = text.match(/(\d+(?:\.\d+)?)\s*(k|thousand|m|million)?\s*(?:active\s*)?(?:daily\s*)?(?:users|dau|mau|people)/i);
  let calculatedQps = 500;

  if (userMatch && !hasExplicitRps) {
    const rawNum = parseFloat(userMatch[1]);
    const multiplier = userMatch[2]?.toLowerCase().startsWith('m') ? 1_000_000 : 1_000;
    const totalUsers = rawNum * multiplier;
    calculatedQps = Math.min(2500, Math.max(50, Math.round((totalUsers * 40) / (14 * 3600) * 2)));
    additions.push(`Expected peak traffic throughput: ~${calculatedQps} requests/second (derived from ${userMatch[0]}).`);
  } else if (!hasExplicitRps) {
    additions.push('Expected peak traffic throughput: ~500 requests/second.');
  }

  if (!hasExplicitP95) {
    additions.push('Latency SLA target: p95 latency under 100 ms.');
  }

  if (!hasExplicitBudget) {
    additions.push('Monthly cloud budget limit: $250/mo.');
  }

  if (/photo|image|feed|stream|catalog|browse|read/i.test(text) && !/90%|80%|write-heavy/i.test(text)) {
    additions.push('Traffic profile: Read-heavy access pattern (~85% reads, 15% writes).');
  }

  return `${conversationContext}\n\n[Architectural System Calibration]:\n${additions.join('\n')}`;
}

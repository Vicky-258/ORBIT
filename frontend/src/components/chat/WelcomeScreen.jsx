import React from 'react';
import {
  Sparkles,
  Hotel,
  GraduationCap,
  Navigation,
  Gamepad2,
  ArrowRight,
  ShieldCheck,
  Cpu
} from 'lucide-react';

export const EXAMPLE_PROMPTS = [
  {
    id: 'hotel-discovery',
    title: 'Hotel Discovery & Booking Platform',
    icon: Hotel,
    description: 'Browse hotels, compare ratings, view map locations, upload reviews, and make bookings.',
    prompt: 'Build a hotel discovery platform where users can browse hotels, compare ratings, view locations on maps, upload reviews, and make bookings.',
  },
  {
    id: 'ai-education',
    title: 'AI-Powered Education Platform',
    icon: GraduationCap,
    description: 'Course catalog browsing, decoupled async AI video generation, and student telemetry.',
    prompt: 'Create an AI-powered education platform where students browse courses, trigger asynchronous AI video generation for lessons, and stream learning progress telemetry.',
  },
  {
    id: 'drone-tracking',
    title: 'Real-Time Drone Fleet Tracking',
    icon: Navigation,
    description: 'Continuous bidirectional GPS tracking, sensor telemetry ingestion, and package bookings.',
    prompt: 'Design a drone delivery tracking system for live GPS positions, high-volume sensor telemetry ingestion, and package delivery bookings.',
  },
  {
    id: 'multiplayer-gaming',
    title: 'Multiplayer Gaming Backend',
    icon: Gamepad2,
    description: 'Live matchmaking, real-time gameplay synchronization, and leaderboard telemetry.',
    prompt: 'Create a multiplayer gaming backend with live player matchmaking, real-time gameplay state synchronization, and high throughput leaderboard telemetry ingestion.',
  },
];

export default function WelcomeScreen({ onSelectPrompt }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-4 sm:px-6 py-12 max-w-3xl mx-auto w-full select-none text-center">
      {/* Icon Badge */}
      <div className="w-12 h-12 rounded-2xl bg-white/[0.06] border border-white/[0.12] flex items-center justify-center text-zinc-200 mb-6 shadow-sm">
        <Sparkles className="w-6 h-6 stroke-[1.75]" />
      </div>

      {/* Main Heading */}
      <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-white mb-2.5">
        What are we building today?
      </h1>

      {/* Supporting Text */}
      <p className="text-sm text-zinc-400 max-w-lg mb-10 leading-relaxed">
        Describe your application idea. I’ll help you understand its architecture, explore infrastructure choices, and evaluate how it performs.
      </p>

      {/* Example Prompt Cards */}
      <div className="w-full grid grid-cols-1 sm:grid-cols-2 gap-3 text-left">
        {EXAMPLE_PROMPTS.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelectPrompt(item.prompt)}
              className="group p-4 rounded-xl border border-white/[0.08] bg-[#121215] hover:bg-[#17171c] hover:border-white/[0.18] transition-all duration-200 text-left flex flex-col justify-between cursor-pointer shadow-xs"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="w-7 h-7 rounded-lg bg-white/[0.05] border border-white/[0.08] flex items-center justify-center text-zinc-300 group-hover:text-white group-hover:border-white/[0.2] transition-colors">
                    <Icon className="w-3.5 h-3.5" />
                  </div>
                  <ArrowRight className="w-3.5 h-3.5 text-zinc-600 group-hover:text-zinc-300 group-hover:translate-x-0.5 transition-all" />
                </div>
                <h3 className="text-xs font-semibold text-zinc-200 group-hover:text-white mb-1">
                  {item.title}
                </h3>
                <p className="text-[11px] text-zinc-500 group-hover:text-zinc-400 line-clamp-2 leading-relaxed">
                  {item.description}
                </p>
              </div>
            </button>
          );
        })}
      </div>

      {/* Subtext info */}
      <div className="mt-8 flex items-center gap-4 text-[11px] text-zinc-600">
        <span className="flex items-center gap-1.5">
          <ShieldCheck className="w-3.5 h-3.5 text-zinc-500" /> Grounded in SimPy Discrete-Event Physics
        </span>
        <span className="w-1 h-1 rounded-full bg-zinc-700" />
        <span className="flex items-center gap-1.5">
          <Cpu className="w-3.5 h-3.5 text-zinc-500" /> Validated Infrastructure Primitives
        </span>
      </div>
    </div>
  );
}

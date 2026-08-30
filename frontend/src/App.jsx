import React, { useState, useEffect, useRef } from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import {
  LayoutDashboard,
  CalendarDays,
  ArrowRight,
  X,
  Send,
  ChevronLeft,
  MoreVertical,
  Clock,
  CheckCircle2,
  Circle,
  Sparkles,
  MessageSquare,
  Loader2,
} from 'lucide-react';
import { createSession, sendMessage, extractAgentText } from './api.js';

function cn(...inputs) {
  return twMerge(clsx(inputs));
}

// ─── Mock Data (for calendar/project detail until Firestore is wired) ───
const MOCK_PROJECTS = [
  {
    id: 'p1',
    title: 'OrionOS',
    summary: 'Final year project for B.Tech — A light operating system with automation capabilities.',
    deadline: 'Sep 7, 2024',
    status: 'active',
    notes: [
      'Learning C is an absolute must, also have to look into assembly.',
      'Should probably not think about a dedicated network stack for now, will look into it if time allows.',
      "Ma'am suggested using a prebuilt base to skip the kernel phase entirely, not sure about that, defeats the whole purpose of \"built an OS\"",
    ],
    tasks: [
      { id: 't1', title: 'C Programming: A Modern Approach', done: true },
      { id: 't2', title: 'The C Programming Language', done: false },
      { id: 't3', title: "Computer Systems: A Programmer's Perspective", done: false },
      { id: 't4', title: 'Operating Systems: Three Easy Pieces', done: false },
      { id: 't5', title: 'MIT xv6 commentary & source code', done: false },
    ],
  },
  {
    id: 'p2',
    title: 'Agentic AI',
    summary: 'Learn agentic AI skill for resume improvement. Complete GEAR program and build portfolio projects.',
    deadline: null,
    status: 'active',
    notes: [],
    tasks: [
      { id: 't6', title: 'Complete GEAR Course Module 1', done: true },
      { id: 't7', title: 'Build first Gemini Enterprise Application', done: false },
      { id: 't8', title: 'Study Agent Fundamentals', done: false },
    ],
  },
  {
    id: 'p3',
    title: 'JEE Preparation',
    summary: 'Develop a one-month study plan for JEE Physics preparation covering optics and mechanics.',
    deadline: '1 month',
    status: 'active',
    notes: [],
    tasks: [
      { id: 't9', title: 'Study physics optics', done: false },
      { id: 't10', title: 'Complete mechanics module', done: false },
    ],
  },
];

const MOCK_SCHEDULE = {
  14: [
    { text: 'C Programming (2 Hours)', done: true, project: 'OrionOS' },
    { text: 'Google GEAR Course (1.5 Hours)', done: false, project: 'Agentic AI' },
    { text: 'Cooking', done: false, project: null },
    { text: 'Movie', done: false, project: null },
  ],
  15: [
    { text: 'Physics Optics (2 Hours)', done: false, project: 'JEE Preparation' },
    { text: 'DSA Practice (1 Hour)', done: false, project: null },
  ],
};

// ─── App ────────────────────────────────────────────────────
export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedProject, setSelectedProject] = useState(null);

  // Agent chat state
  const [sessionId, setSessionId] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [bottomInput, setBottomInput] = useState('');
  const [isAgentThinking, setIsAgentThinking] = useState(false);
  const chatEndRef = useRef(null);

  // Scroll chat to bottom when new messages arrive
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  // Initialize ADK session on first load
  useEffect(() => {
    createSession()
      .then((session) => {
        setSessionId(session.id);
        console.log('ADK session created:', session.id);
      })
      .catch((err) => {
        console.error('Failed to create ADK session:', err);
      });
  }, []);

  const sendToAgent = async (text) => {
    if (!text.trim() || !sessionId) return;

    // Add user message to chat
    setChatMessages((prev) => [...prev, { role: 'user', text }]);
    setIsAgentThinking(true);

    try {
      // Collect all SSE events
      const events = [];
      await sendMessage(sessionId, text, (event) => {
        events.push(event);
      });

      // Extract the agent's text response
      const agentReply = extractAgentText(events);
      if (agentReply) {
        setChatMessages((prev) => [...prev, { role: 'assistant', text: agentReply }]);
      }
    } catch (err) {
      console.error('Agent error:', err);
      setChatMessages((prev) => [
        ...prev,
        { role: 'assistant', text: '⚠️ Something went wrong. Please try again.' },
      ]);
    } finally {
      setIsAgentThinking(false);
    }
  };

  const handleBottomSend = () => {
    if (!bottomInput.trim()) return;
    const msg = bottomInput;
    setBottomInput('');
    setSidebarOpen(true);
    sendToAgent(msg);
  };

  const handleChatSend = () => {
    if (!chatInput.trim()) return;
    const msg = chatInput;
    setChatInput('');
    sendToAgent(msg);
  };

  const renderContent = () => {
    if (selectedProject) {
      return <ProjectDetail project={selectedProject} onBack={() => setSelectedProject(null)} />;
    }
    if (activeTab === 'dashboard') {
      return <Dashboard onSelectProject={setSelectedProject} />;
    }
    return <CalendarView />;
  };

  return (
    <div className="flex h-screen overflow-hidden">
      {/* ── Main Column ── */}
      <div className="flex-1 flex flex-col min-w-0 transition-all duration-300">
        {/* Top Nav */}
        <nav className="flex items-center gap-1 px-6 py-4 border-b border-borderLight bg-white">
          <NavTab
            icon={<LayoutDashboard size={18} />}
            label="Dashboard"
            active={activeTab === 'dashboard' && !selectedProject}
            onClick={() => { setActiveTab('dashboard'); setSelectedProject(null); }}
          />
          <NavTab
            icon={<CalendarDays size={18} />}
            label="Calendar"
            active={activeTab === 'calendar' && !selectedProject}
            onClick={() => { setActiveTab('calendar'); setSelectedProject(null); }}
          />
          <div className="ml-auto flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-colors",
                sidebarOpen
                  ? "bg-accentLight text-accentText"
                  : "text-textSecondary hover:bg-gray-100"
              )}
            >
              <MessageSquare size={16} />
              <span className="hidden sm:inline">Agent</span>
            </button>
            <div className="w-8 h-8 rounded-full bg-accent text-white flex items-center justify-center text-sm font-medium">
              A
            </div>
          </div>
        </nav>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto p-6 lg:p-8">{renderContent()}</main>

        {/* Bottom Input */}
        <div className="px-6 pb-6 pt-2">
          <div className="max-w-2xl mx-auto">
            <div className="flex items-center bg-white border border-borderLight rounded-full shadow-card px-5 py-1 focus-within:border-borderFocus focus-within:shadow-cardHover transition-all">
              <Sparkles size={20} className="text-textTertiary mr-3 flex-shrink-0" />
              <input
                type="text"
                value={bottomInput}
                onChange={(e) => setBottomInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleBottomSend()}
                placeholder="What's on the agenda today?"
                className="flex-1 py-3 text-base outline-none bg-transparent placeholder:text-textTertiary"
              />
              <button
                onClick={handleBottomSend}
                className="ml-2 p-2 rounded-full text-textTertiary hover:text-accent hover:bg-accentLight transition-colors"
              >
                <Send size={18} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* ── Agent Sidebar ── */}
      <aside
        className={cn(
          "h-full bg-white border-l border-borderLight flex flex-col transition-all duration-300 ease-in-out overflow-hidden shadow-sidebar",
          sidebarOpen ? "w-[380px] min-w-[380px]" : "w-0 min-w-0 border-l-0 shadow-none"
        )}
      >
        {/* Sidebar Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-borderLight flex-shrink-0">
          <div className="flex items-center gap-2">
            <Sparkles size={18} className="text-accent" />
            <span className="font-semibold text-base text-textPrimary">Gemini 3.5 Flash</span>
          </div>
          <button
            onClick={() => setSidebarOpen(false)}
            className="p-1.5 rounded-full hover:bg-gray-100 text-textSecondary transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Chat Messages */}
        <div className="flex-1 overflow-y-auto p-5 flex flex-col gap-5">
          {chatMessages.length === 0 && (
            <div className="flex-1 flex flex-col items-center justify-center text-center text-textTertiary py-12">
              <Sparkles size={32} className="mb-3 text-accent opacity-50" />
              <p className="text-sm">Send a message to start chatting with your agent.</p>
            </div>
          )}
          {chatMessages.map((msg, i) =>
            msg.role === 'user' ? (
              <div key={i} className="self-end max-w-[80%]">
                <div className="bg-accent text-white px-4 py-2.5 rounded-2xl rounded-br-md text-sm leading-relaxed">
                  {msg.text}
                </div>
              </div>
            ) : (
              <div key={i} className="self-start max-w-[90%]">
                <div className="bg-surface px-4 py-3 rounded-2xl rounded-bl-md text-sm leading-relaxed text-textPrimary whitespace-pre-line">
                  {msg.text}
                </div>
              </div>
            )
          )}
          {isAgentThinking && (
            <div className="self-start">
              <div className="bg-surface px-4 py-3 rounded-2xl rounded-bl-md flex items-center gap-2 text-sm text-textTertiary">
                <Loader2 size={16} className="animate-spin" />
                Thinking...
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Chat Input */}
        <div className="p-4 border-t border-borderLight flex-shrink-0">
          <div className="flex items-center bg-surface rounded-full px-4 py-1 border border-borderLight focus-within:border-borderFocus transition-colors">
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleChatSend()}
              placeholder="Reply to Gemini..."
              className="flex-1 py-2.5 text-sm bg-transparent outline-none placeholder:text-textTertiary"
            />
            <button
              onClick={handleChatSend}
              disabled={isAgentThinking}
              className="ml-1 p-1.5 rounded-full text-textTertiary hover:text-accent transition-colors disabled:opacity-50"
            >
              <Send size={16} />
            </button>
          </div>
        </div>
      </aside>
    </div>
  );
}

// ─── Nav Tab ────────────────────────────────────────────────
function NavTab({ icon, label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-colors",
        active ? "bg-accentLight text-accentText" : "text-textSecondary hover:bg-gray-100"
      )}
    >
      {icon}
      {label}
    </button>
  );
}

// ─── Dashboard ──────────────────────────────────────────────
function Dashboard({ onSelectProject }) {
  return (
    <div>
      <h1 className="text-2xl font-semibold text-textPrimary mb-6">Projects</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
        {MOCK_PROJECTS.map((project) => (
          <ProjectCard key={project.id} project={project} onClick={() => onSelectProject(project)} />
        ))}
      </div>
    </div>
  );
}

// ─── Project Card ───────────────────────────────────────────
function ProjectCard({ project, onClick }) {
  const completedCount = project.tasks.filter((t) => t.done).length;
  return (
    <div
      onClick={onClick}
      className="bg-surfaceCard rounded-card border border-borderLight p-5 cursor-pointer shadow-card hover:shadow-cardHover transition-shadow duration-200 flex flex-col justify-between"
    >
      <div className="flex items-center gap-2 mb-3">
        <span className="inline-flex items-center gap-1 bg-tagBg text-tagText text-xs font-medium px-2.5 py-1 rounded-full">
          📋 Project
        </span>
        {project.status === 'completed' && (
          <span className="inline-flex items-center gap-1 bg-successBg text-successText text-xs font-medium px-2.5 py-1 rounded-full">
            ✓ Completed
          </span>
        )}
      </div>
      <h3 className="text-lg font-semibold text-textPrimary mb-1.5 line-clamp-1">{project.title}</h3>
      <p className="text-sm text-textSecondary leading-relaxed mb-4 line-clamp-3">{project.summary}</p>
      <div className="flex items-center justify-between mt-auto pt-3 border-t border-borderLight">
        <div className="flex items-center gap-4 text-xs text-textTertiary">
          {project.deadline && (
            <span className="flex items-center gap-1"><Clock size={13} />{project.deadline}</span>
          )}
          <span>{completedCount}/{project.tasks.length} tasks</span>
        </div>
        <div className="w-8 h-8 rounded-full bg-accentLight flex items-center justify-center text-accent hover:bg-accent hover:text-white transition-colors">
          <ArrowRight size={16} />
        </div>
      </div>
    </div>
  );
}

// ─── Project Detail ─────────────────────────────────────────
function ProjectDetail({ project, onBack }) {
  return (
    <div>
      <button onClick={onBack} className="flex items-center gap-1.5 text-sm text-textSecondary hover:text-accentText font-medium mb-5 transition-colors">
        <ChevronLeft size={16} /> Back to Projects
      </button>
      <div className="mb-8">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-semibold text-textPrimary mb-2">{project.title}</h1>
            <p className="text-base text-textSecondary leading-relaxed max-w-xl">{project.summary}</p>
          </div>
          {project.deadline && (
            <span className="flex items-center gap-1.5 text-sm text-textTertiary bg-surface px-3 py-1.5 rounded-full border border-borderLight flex-shrink-0">
              <Clock size={14} />{project.deadline}
            </span>
          )}
        </div>
      </div>
      <div className="flex flex-col lg:flex-row gap-8">
        {project.notes.length > 0 && (
          <div className="w-full lg:w-1/2">
            <h2 className="text-lg font-semibold text-textPrimary mb-4">Notes</h2>
            <div className="bg-surfaceCard rounded-card border border-borderLight p-5 space-y-4">
              {project.notes.map((note, i) => (
                <div key={i} className="flex gap-3 text-sm text-textSecondary leading-relaxed">
                  <span className="text-textTertiary font-medium flex-shrink-0">{i + 1}.</span>
                  <p>{note}</p>
                </div>
              ))}
            </div>
          </div>
        )}
        <div className={cn("w-full", project.notes.length > 0 ? "lg:w-1/2" : "lg:w-2/3")}>
          <h2 className="text-lg font-semibold text-textPrimary mb-4">Tasks</h2>
          <div className="space-y-3">
            {project.tasks.map((task) => (
              <div key={task.id} className={cn("flex items-center gap-3 bg-surfaceCard rounded-card border border-borderLight px-5 py-3.5 transition-shadow hover:shadow-card", task.done && "bg-surface")}>
                {task.done ? <CheckCircle2 size={20} className="text-accent flex-shrink-0" /> : <Circle size={20} className="text-borderLight flex-shrink-0" />}
                <span className={cn("text-sm flex-1", task.done ? "text-textTertiary line-through" : "text-textPrimary")}>{task.title}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Calendar View ──────────────────────────────────────────
function CalendarView() {
  const [selectedDay, setSelectedDay] = useState(14);
  const daysInMonth = 31;
  const startDay = 3;
  const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const today = 30;
  const schedule = MOCK_SCHEDULE[selectedDay] || [];

  return (
    <div className="flex flex-col lg:flex-row gap-8">
      <div className="w-full lg:w-2/5">
        <h1 className="text-2xl font-semibold text-textPrimary mb-1">Calendar</h1>
        <p className="text-sm text-textSecondary mb-6">August 2026</p>
        <div className="bg-surfaceCard rounded-card border border-borderLight p-5">
          <div className="grid grid-cols-7 mb-3">
            {dayNames.map((d) => (
              <div key={d} className="text-center text-xs font-medium text-textTertiary py-2">{d}</div>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-y-1">
            {Array.from({ length: startDay }).map((_, i) => <div key={`e-${i}`} />)}
            {Array.from({ length: daysInMonth }).map((_, i) => {
              const day = i + 1;
              const hasEvents = MOCK_SCHEDULE[day] !== undefined;
              const isSelected = day === selectedDay;
              const isToday = day === today;
              return (
                <button key={day} onClick={() => setSelectedDay(day)} className={cn("w-10 h-10 mx-auto rounded-full flex flex-col items-center justify-center text-sm font-medium relative transition-colors", isSelected ? "bg-accent text-white" : isToday ? "bg-accentLight text-accentText" : "text-textPrimary hover:bg-gray-100")}>
                  {day}
                  {hasEvents && !isSelected && <span className="absolute bottom-1 w-1 h-1 rounded-full bg-accent" />}
                </button>
              );
            })}
          </div>
        </div>
      </div>
      <div className="w-full lg:w-3/5">
        <div className="mb-6">
          <h2 className="text-2xl font-semibold text-textPrimary mb-1">Schedule</h2>
          <p className="text-sm text-textSecondary">{selectedDay === today ? 'Today' : `August ${selectedDay}`}{schedule.length > 0 && ` · ${schedule.length} items`}</p>
        </div>
        {schedule.length === 0 ? (
          <div className="bg-surfaceCard rounded-card border border-borderLight p-8 text-center">
            <CalendarDays size={32} className="text-textTertiary mx-auto mb-3" />
            <p className="text-sm text-textTertiary">No tasks scheduled for this day.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {schedule.map((item, i) => (
              <div key={i} className={cn("flex items-center gap-4 bg-surfaceCard rounded-card border border-borderLight px-5 py-4 transition-shadow hover:shadow-card", item.done && "bg-surface")}>
                <span className="text-sm text-textTertiary font-medium w-6 text-center flex-shrink-0">{i + 1}.</span>
                {item.done ? <CheckCircle2 size={20} className="text-accent flex-shrink-0" /> : <Circle size={20} className="text-borderLight flex-shrink-0" />}
                <div className="flex-1 min-w-0">
                  <p className={cn("text-sm font-medium", item.done ? "text-textTertiary line-through" : "text-textPrimary")}>{item.text}</p>
                  {item.project && <p className="text-xs text-textTertiary mt-0.5">{item.project}</p>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

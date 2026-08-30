import React, { useState, useEffect, useRef, useCallback } from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import {
  LayoutDashboard, CalendarDays, ArrowRight, X, Send,
  ChevronLeft, Clock, CheckCircle2, Circle, Sparkles,
  MessageSquare, Loader2, RefreshCw,
} from 'lucide-react';
import {
  createSession, sendMessage, extractAgentText,
  fetchProjects, fetchProjectDetail, fetchSchedule, toggleTask
} from './api.js';

function cn(...inputs) { return twMerge(clsx(inputs)); }

// ─── App Component ───────────────────────────────────────────────
export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedProjectId, setSelectedProjectId] = useState(null);

  // Live Firestore State
  const [projects, setProjects] = useState([]);
  const [scheduleTasks, setScheduleTasks] = useState([]);
  const [isLoadingData, setIsLoadingData] = useState(true);

  // Agent Chat State
  const [sessionId, setSessionId] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [bottomInput, setBottomInput] = useState('');
  const [isAgentThinking, setIsAgentThinking] = useState(false);
  const chatEndRef = useRef(null);

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages, isAgentThinking]);

  // Load Firestore Data
  const loadData = useCallback(async () => {
    setIsLoadingData(true);
    try {
      const [projList, schedList] = await Promise.all([
        fetchProjects(),
        fetchSchedule(),
      ]);
      setProjects(projList);
      setScheduleTasks(schedList);
    } catch (err) {
      console.error('Failed to load Firestore data:', err);
    } finally {
      setIsLoadingData(false);
    }
  }, []);

  // Initialize ADK session & fetch data on mount
  useEffect(() => {
    createSession()
      .then((s) => {
        setSessionId(s.id);
        console.log('ADK Session:', s.id);
      })
      .catch((e) => console.error('Session error:', e));

    loadData();
  }, [loadData]);

  // Send message to Agent
  const sendToAgent = async (text) => {
    if (!text.trim() || !sessionId) return;
    setChatMessages((p) => [...p, { role: 'user', text }]);
    setIsAgentThinking(true);

    try {
      const events = [];
      await sendMessage(sessionId, text, (ev) => events.push(ev));
      const reply = extractAgentText(events);
      if (reply) {
        setChatMessages((p) => [...p, { role: 'assistant', text: reply }]);
      }
      // Refresh Firestore data after agent responds to show newly created tasks/projects
      setTimeout(loadData, 1500);
    } catch (err) {
      console.error('Agent error:', err);
      setChatMessages((p) => [
        ...p,
        { role: 'assistant', text: '⚠️ Something went wrong contacting the agent. Please check the backend server.' },
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

  const handleToggleTask = async (taskId, currentDone) => {
    try {
      await toggleTask(taskId, !currentDone);
      // Optimistically update schedule list
      setScheduleTasks((prev) =>
        prev.map((t) => (t.id === taskId ? { ...t, done: !currentDone } : t))
      );
      // Reload full data
      loadData();
    } catch (err) {
      console.error('Failed to toggle task:', err);
    }
  };

  const renderContent = () => {
    if (selectedProjectId) {
      return (
        <ProjectDetail
          projectId={selectedProjectId}
          onBack={() => {
            setSelectedProjectId(null);
            loadData();
          }}
        />
      );
    }
    if (activeTab === 'dashboard') {
      return (
        <Dashboard
          projects={projects}
          isLoading={isLoadingData}
          onRefresh={loadData}
          onSelectProject={(p) => setSelectedProjectId(p.id)}
        />
      );
    }
    return (
      <CalendarView
        tasks={scheduleTasks}
        isLoading={isLoadingData}
        onToggleTask={handleToggleTask}
        onRefresh={loadData}
      />
    );
  };

  return (
    <div className="flex h-screen overflow-hidden">
      {/* ── Main Column ── */}
      <div className="flex-1 flex flex-col min-w-0 transition-all duration-300">
        <nav className="flex items-center gap-1 px-6 py-4 border-b border-borderLight bg-white">
          <NavTab
            icon={<LayoutDashboard size={18} />}
            label="Dashboard"
            active={activeTab === 'dashboard' && !selectedProjectId}
            onClick={() => { setActiveTab('dashboard'); setSelectedProjectId(null); }}
          />
          <NavTab
            icon={<CalendarDays size={18} />}
            label="Calendar"
            active={activeTab === 'calendar' && !selectedProjectId}
            onClick={() => { setActiveTab('calendar'); setSelectedProjectId(null); }}
          />

          <div className="ml-auto flex items-center gap-3">
            <button
              onClick={loadData}
              title="Refresh Firestore Data"
              className="p-2 rounded-full text-textSecondary hover:bg-gray-100 transition-colors"
            >
              <RefreshCw size={16} className={cn(isLoadingData && "animate-spin text-accent")} />
            </button>

            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-colors",
                sidebarOpen ? "bg-accentLight text-accentText" : "text-textSecondary hover:bg-gray-100"
              )}
            >
              <MessageSquare size={16} />
              <span className="hidden sm:inline">Agent Chat</span>
            </button>

            <div className="w-8 h-8 rounded-full bg-accent text-white flex items-center justify-center text-sm font-medium">
              A
            </div>
          </div>
        </nav>

        <main className="flex-1 overflow-y-auto p-6 lg:p-8">
          {renderContent()}
        </main>

        {/* Bottom Input */}
        <div className="px-6 pb-6 pt-2">
          <div className="max-w-2xl mx-auto">
            <div className="flex items-center bg-white border border-borderLight rounded-full shadow-card px-5 py-1 focus-within:border-borderFocus focus-within:shadow-cardHover transition-all">
              <Sparkles size={20} className="text-accent mr-3 flex-shrink-0" />
              <input
                type="text"
                value={bottomInput}
                onChange={(e) => setBottomInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleBottomSend()}
                placeholder="What's on the agenda today? (Ask agent to plan, study, research...)"
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
          sidebarOpen ? "w-[400px] min-w-[400px]" : "w-0 min-w-0 border-l-0 shadow-none"
        )}
      >
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

        <div className="flex-1 overflow-y-auto p-5 flex flex-col gap-5">
          {chatMessages.length === 0 && (
            <div className="flex-1 flex flex-col items-center justify-center text-center text-textTertiary py-12">
              <Sparkles size={32} className="mb-3 text-accent opacity-50" />
              <p className="text-sm font-medium text-textPrimary mb-1">Cognitive Canvas Agent</p>
              <p className="text-xs text-textSecondary max-w-xs">
                Tell me a project, exam, or goal you want to plan. I'll structure it into actionable tasks!
              </p>
            </div>
          )}

          {chatMessages.map((msg, i) =>
            msg.role === 'user' ? (
              <div key={i} className="self-end max-w-[85%]">
                <div className="bg-accent text-white px-4 py-2.5 rounded-2xl rounded-br-md text-sm leading-relaxed shadow-sm">
                  {msg.text}
                </div>
              </div>
            ) : (
              <div key={i} className="self-start max-w-[90%]">
                <div className="bg-surface border border-borderLight px-4 py-3 rounded-2xl rounded-bl-md text-sm leading-relaxed text-textPrimary whitespace-pre-line shadow-sm">
                  {msg.text}
                </div>
              </div>
            )
          )}

          {isAgentThinking && (
            <div className="self-start">
              <div className="bg-surface border border-borderLight px-4 py-3 rounded-2xl rounded-bl-md flex items-center gap-2 text-sm text-textSecondary shadow-sm">
                <Loader2 size={16} className="animate-spin text-accent" />
                Thinking & extracting plan...
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

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

// ─── Dashboard View ──────────────────────────────────────────────
function Dashboard({ projects, isLoading, onRefresh, onSelectProject }) {
  if (isLoading && projects.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-textTertiary">
        <Loader2 size={32} className="animate-spin text-accent mb-3" />
        <p className="text-sm">Loading projects from Firestore...</p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-textPrimary">Events & Projects</h1>
          <p className="text-sm text-textSecondary mt-0.5">
            {projects.length} {projects.length === 1 ? 'project' : 'projects'} saved in Firestore
          </p>
        </div>
      </div>

      {projects.length === 0 ? (
        <div className="bg-surfaceCard rounded-card border border-borderLight p-12 text-center shadow-card">
          <Sparkles size={36} className="text-accent mx-auto mb-3 opacity-60" />
          <h3 className="text-lg font-medium text-textPrimary mb-1">No Projects Found</h3>
          <p className="text-sm text-textSecondary max-w-md mx-auto mb-6">
            Ask the agent below (e.g. "Create a 2-week plan to study Operating Systems") to create your first project!
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {projects.map((p) => (
            <ProjectCard key={p.id} project={p} onClick={() => onSelectProject(p)} />
          ))}
        </div>
      )}
    </div>
  );
}

function ProjectCard({ project, onClick }) {
  const isCompleted = project.status === 'completed' || (project.taskCount > 0 && project.completedCount === project.taskCount);

  return (
    <div
      onClick={onClick}
      className="bg-surfaceCard rounded-card border border-borderLight p-5 cursor-pointer shadow-card hover:shadow-cardHover transition-shadow duration-200 flex flex-col justify-between"
    >
      <div>
        <div className="flex items-center gap-2 mb-3">
          <span className="inline-flex items-center gap-1 bg-tagBg text-tagText text-xs font-medium px-2.5 py-1 rounded-full">
            📋 Project
          </span>
          {isCompleted && (
            <span className="inline-flex items-center gap-1 bg-successBg text-successText text-xs font-medium px-2.5 py-1 rounded-full">
              ✓ Completed
            </span>
          )}
        </div>
        <h3 className="text-lg font-semibold text-textPrimary mb-1.5 line-clamp-1">{project.title}</h3>
        <p className="text-sm text-textSecondary leading-relaxed mb-4 line-clamp-3">
          {project.summary || 'No description provided.'}
        </p>
      </div>

      <div className="flex items-center justify-between mt-auto pt-3 border-t border-borderLight">
        <div className="flex items-center gap-4 text-xs text-textTertiary">
          {project.deadline && (
            <span className="flex items-center gap-1">
              <Clock size={13} />
              {project.deadline}
            </span>
          )}
          <span>{project.completedCount || 0}/{project.taskCount || 0} tasks</span>
        </div>
        <div className="w-8 h-8 rounded-full bg-accentLight flex items-center justify-center text-accent hover:bg-accent hover:text-white transition-colors">
          <ArrowRight size={16} />
        </div>
      </div>
    </div>
  );
}

// ─── Project Detail View ─────────────────────────────────────────
function ProjectDetail({ projectId, onBack }) {
  const [project, setProject] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const loadProject = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await fetchProjectDetail(projectId);
      setProject(data);
    } catch (err) {
      console.error('Failed to load project:', err);
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadProject();
  }, [loadProject]);

  const handleTaskToggle = async (taskId, currentDone) => {
    try {
      await toggleTask(taskId, !currentDone);
      setProject((prev) => ({
        ...prev,
        tasks: prev.tasks.map((t) => (t.id === taskId ? { ...t, done: !currentDone } : t)),
      }));
    } catch (err) {
      console.error('Failed to toggle task:', err);
    }
  };

  if (isLoading || !project) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-textTertiary">
        <Loader2 size={32} className="animate-spin text-accent mb-3" />
        <p className="text-sm">Loading project details...</p>
      </div>
    );
  }

  return (
    <div>
      <button
        onClick={onBack}
        className="flex items-center gap-1.5 text-sm text-textSecondary hover:text-accentText font-medium mb-5 transition-colors"
      >
        <ChevronLeft size={16} /> Back to Projects
      </button>

      <div className="mb-8 flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-semibold text-textPrimary mb-2">{project.title}</h1>
          <p className="text-base text-textSecondary leading-relaxed max-w-2xl">{project.summary}</p>
        </div>
        {project.deadline && (
          <span className="flex items-center gap-1.5 text-sm text-textTertiary bg-surface px-3.5 py-1.5 rounded-full border border-borderLight flex-shrink-0">
            <Clock size={14} />
            {project.deadline}
          </span>
        )}
      </div>

      <div className="flex flex-col lg:flex-row gap-8">
        {/* Notes / Research Findings */}
        {project.notes && project.notes.length > 0 && (
          <div className="w-full lg:w-1/2">
            <h2 className="text-lg font-semibold text-textPrimary mb-4">Notes & Findings</h2>
            <div className="bg-surfaceCard rounded-card border border-borderLight p-5 space-y-4 shadow-card">
              {project.notes.map((note, i) => (
                <div key={i} className="flex gap-3 text-sm text-textSecondary leading-relaxed">
                  <span className="text-accent font-medium flex-shrink-0">{i + 1}.</span>
                  <p>{note}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tasks List */}
        <div className={cn("w-full", project.notes && project.notes.length > 0 ? "lg:w-1/2" : "lg:w-2/3")}>
          <h2 className="text-lg font-semibold text-textPrimary mb-4">Actionable Tasks</h2>
          {(!project.tasks || project.tasks.length === 0) ? (
            <div className="bg-surfaceCard rounded-card border border-borderLight p-8 text-center text-textTertiary shadow-card">
              No tasks generated for this project yet.
            </div>
          ) : (
            <div className="space-y-3">
              {project.tasks.map((task) => (
                <div
                  key={task.id}
                  onClick={() => handleTaskToggle(task.id, task.done)}
                  className={cn(
                    "flex items-center gap-3 bg-surfaceCard rounded-card border border-borderLight px-5 py-3.5 transition-all hover:shadow-card cursor-pointer select-none",
                    task.done && "bg-surface opacity-75"
                  )}
                >
                  {task.done ? (
                    <CheckCircle2 size={20} className="text-accent flex-shrink-0" />
                  ) : (
                    <Circle size={20} className="text-borderLight hover:text-accent flex-shrink-0" />
                  )}
                  <div className="flex-1 min-w-0">
                    <span className={cn(
                      "text-sm font-medium",
                      task.done ? "text-textTertiary line-through" : "text-textPrimary"
                    )}>
                      {task.title}
                    </span>
                    {task.details && (
                      <p className="text-xs text-textTertiary mt-0.5">{task.details}</p>
                    )}
                  </div>
                  {task.estimatedMinutes && (
                    <span className="text-xs text-textTertiary bg-tagBg px-2 py-0.5 rounded">
                      {task.estimatedMinutes}m
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Calendar View ───────────────────────────────────────────────
function CalendarView({ tasks, isLoading, onToggleTask }) {
  const [selectedDay, setSelectedDay] = useState(30);
  const daysInMonth = 31;
  const startDay = 3;
  const today = 30;
  const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

  return (
    <div className="flex flex-col lg:flex-row gap-8">
      {/* Left Calendar Grid */}
      <div className="w-full lg:w-2/5">
        <h1 className="text-2xl font-semibold text-textPrimary mb-1">Calendar</h1>
        <p className="text-sm text-textSecondary mb-6">August 2026</p>

        <div className="bg-surfaceCard rounded-card border border-borderLight p-5 shadow-card">
          <div className="grid grid-cols-7 mb-3">
            {dayNames.map((d) => (
              <div key={d} className="text-center text-xs font-medium text-textTertiary py-2">
                {d}
              </div>
            ))}
          </div>

          <div className="grid grid-cols-7 gap-y-1">
            {Array.from({ length: startDay }).map((_, i) => (
              <div key={`e-${i}`} />
            ))}
            {Array.from({ length: daysInMonth }).map((_, i) => {
              const day = i + 1;
              const isSelected = day === selectedDay;
              const isToday = day === today;

              return (
                <button
                  key={day}
                  onClick={() => setSelectedDay(day)}
                  className={cn(
                    "w-10 h-10 mx-auto rounded-full flex flex-col items-center justify-center text-sm font-medium relative transition-colors",
                    isSelected
                      ? "bg-accent text-white"
                      : isToday
                      ? "bg-accentLight text-accentText"
                      : "text-textPrimary hover:bg-gray-100"
                  )}
                >
                  {day}
                  {isToday && !isSelected && (
                    <span className="absolute bottom-1 w-1 h-1 rounded-full bg-accent" />
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Right Schedule List */}
      <div className="w-full lg:w-3/5">
        <div className="flex items-baseline justify-between mb-6">
          <div>
            <h2 className="text-2xl font-semibold text-textPrimary mb-1">Schedule</h2>
            <p className="text-sm text-textSecondary">
              {selectedDay === today ? 'Today' : `August ${selectedDay}`} · {tasks.length} active tasks
            </p>
          </div>
        </div>

        {isLoading ? (
          <div className="bg-surfaceCard rounded-card border border-borderLight p-12 text-center shadow-card">
            <Loader2 size={24} className="animate-spin text-accent mx-auto mb-2" />
            <p className="text-sm text-textTertiary">Loading schedule from Firestore...</p>
          </div>
        ) : tasks.length === 0 ? (
          <div className="bg-surfaceCard rounded-card border border-borderLight p-8 text-center shadow-card">
            <CalendarDays size={32} className="text-textTertiary mx-auto mb-3" />
            <p className="text-sm text-textTertiary">No scheduled tasks found in Firestore.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {tasks.map((item, i) => (
              <div
                key={item.id}
                onClick={() => onToggleTask(item.id, item.done)}
                className={cn(
                  "flex items-center gap-4 bg-surfaceCard rounded-card border border-borderLight px-5 py-4 transition-all hover:shadow-card cursor-pointer select-none",
                  item.done && "bg-surface opacity-75"
                )}
              >
                <span className="text-sm text-textTertiary font-medium w-6 text-center flex-shrink-0">
                  {i + 1}.
                </span>
                {item.done ? (
                  <CheckCircle2 size={20} className="text-accent flex-shrink-0" />
                ) : (
                  <Circle size={20} className="text-borderLight hover:text-accent flex-shrink-0" />
                )}
                <div className="flex-1 min-w-0">
                  <p className={cn(
                    "text-sm font-medium",
                    item.done ? "text-textTertiary line-through" : "text-textPrimary"
                  )}>
                    {item.text}
                  </p>
                  {item.project && (
                    <p className="text-xs text-textTertiary mt-0.5">{item.project}</p>
                  )}
                </div>
                {item.estimatedMinutes && (
                  <span className="text-xs text-textTertiary bg-tagBg px-2 py-0.5 rounded">
                    {item.estimatedMinutes}m
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

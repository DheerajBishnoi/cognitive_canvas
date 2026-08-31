import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import {
  LayoutDashboard, CalendarDays, ArrowRight, X, Send,
  ChevronLeft, Clock, CheckCircle2, Circle, Sparkles,
  MessageSquare, Loader2, RefreshCw, AlertTriangle, ShieldCheck,
  Plus, Calendar as CalendarIcon, Trash2, Edit3,
} from 'lucide-react';
import {
  sendChatMessage,
  fetchProjects, fetchProjectDetail, fetchSchedule, toggleTask, createTask,
  deleteProject, updateProject, deleteTask,
} from './api.js';

function cn(...inputs) { return twMerge(clsx(inputs)); }

function formatModelName(name) {
  if (!name) return 'Gemini 3.5 Flash';
  if (name.includes('3.5')) return 'Gemini 3.5 Flash';
  if (name.includes('3.1')) return 'Gemini 3.1 Flash Lite';
  if (name.includes('2.5')) return 'Gemini 2.5 Flash';
  return name;
}

// ─── App Component ───────────────────────────────────────────────
export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedProjectId, setSelectedProjectId] = useState(null);

  // Live Firestore State
  const [projects, setProjects] = useState([]);
  const [scheduleTasks, setScheduleTasks] = useState([]);
  const [isLoadingData, setIsLoadingData] = useState(true);

  // Agent Chat State with Fallback Support
  const [currentModel, setCurrentModel] = useState('gemini-3.5-flash');
  const [isFallbackActive, setIsFallbackActive] = useState(false);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [bottomInput, setBottomInput] = useState('');
  const [isAgentThinking, setIsAgentThinking] = useState(false);
  const [fallbackNotice, setFallbackNotice] = useState(null);
  const chatEndRef = useRef(null);

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages, isAgentThinking, fallbackNotice]);

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

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Send message to Agent with automatic Quota Fallback
  const sendToAgent = async (text) => {
    if (!text.trim()) return;

    setChatMessages((prev) => [...prev, { role: 'user', text }]);
    setIsAgentThinking(true);
    setFallbackNotice(null);

    let incomingResponse = '';
    let responseModel = currentModel;
    let fallbackOccurred = false;

    try {
      await sendChatMessage(text, (event) => {
        if (event.type === 'fallback_warning') {
          fallbackOccurred = true;
          setIsFallbackActive(true);
          setCurrentModel(event.fallback_model);
          setFallbackNotice({
            failedModel: formatModelName(event.failed_model),
            fallbackModel: formatModelName(event.fallback_model),
            reason: event.reason || 'High demand / Quota limit',
            message: event.message || `Switched to ${formatModelName(event.fallback_model)} automatically.`,
          });
        } else if (event.type === 'text') {
          incomingResponse += event.text;
          if (event.model) {
            responseModel = event.model;
            setCurrentModel(event.model);
          }
          if (event.is_fallback) {
            setIsFallbackActive(true);
          }
        } else if (event.type === 'done') {
          if (event.model) {
            responseModel = event.model;
            setCurrentModel(event.model);
          }
          if (event.is_fallback) {
            setIsFallbackActive(true);
          }
        } else if (event.type === 'error') {
          throw new Error(event.message);
        }
      });

      if (incomingResponse) {
        setChatMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            text: incomingResponse,
            model: formatModelName(responseModel),
            isFallback: fallbackOccurred,
          },
        ]);
      }

      // Refresh Firestore data after planning completes
      setTimeout(loadData, 1500);
    } catch (err) {
      console.error('Agent chat error:', err);
      setChatMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: err.message || 'Check server connection.',
          isError: true,
        },
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
      setScheduleTasks((prev) =>
        prev.map((t) => (t.id === taskId ? { ...t, done: !currentDone } : t))
      );
      loadData();
    } catch (err) {
      console.error('Failed to toggle task:', err);
    }
  };

  const handleCreateTask = async (newTaskData) => {
    try {
      await createTask(newTaskData);
      loadData();
    } catch (err) {
      console.error('Failed to create task:', err);
    }
  };

  const handleDeleteTask = async (taskId) => {
    try {
      await deleteTask(taskId);
      setScheduleTasks((prev) => prev.filter((t) => t.id !== taskId));
      loadData();
    } catch (err) {
      console.error('Failed to delete task:', err);
    }
  };

  const handleDeleteProject = async (projectId) => {
    try {
      await deleteProject(projectId);
      setProjects((prev) => prev.filter((p) => p.id !== projectId));
      if (selectedProjectId === projectId) {
        setSelectedProjectId(null);
      }
      loadData();
    } catch (err) {
      console.error('Failed to delete project:', err);
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
          onDeleteProject={handleDeleteProject}
          onDeleteTask={handleDeleteTask}
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
          onDeleteProject={handleDeleteProject}
        />
      );
    }
    return (
      <CalendarView
        tasks={scheduleTasks}
        isLoading={isLoadingData}
        onToggleTask={handleToggleTask}
        onCreateTask={handleCreateTask}
        onDeleteTask={handleDeleteTask}
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
              {isFallbackActive && (
                <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" title="Fallback model active" />
              )}
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
                placeholder="What's on the agenda today? (e.g. Plan a 2-week Linux study schedule...)"
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
          sidebarOpen ? "w-[420px] min-w-[420px]" : "w-0 min-w-0 border-l-0 shadow-none"
        )}
      >
        {/* Sidebar Header with Dynamic Model Badge */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-borderLight flex-shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            <Sparkles size={18} className="text-accent flex-shrink-0" />
            <div className="flex flex-col min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="font-semibold text-sm text-textPrimary truncate">
                  {formatModelName(currentModel)}
                </span>
                {isFallbackActive ? (
                  <span className="text-[10px] font-semibold bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded-full uppercase tracking-wider flex items-center gap-1 flex-shrink-0">
                    <AlertTriangle size={10} /> Fallback
                  </span>
                ) : (
                  <span className="text-[10px] font-semibold bg-emerald-100 text-emerald-800 px-1.5 py-0.5 rounded-full uppercase tracking-wider flex items-center gap-1 flex-shrink-0">
                    <ShieldCheck size={10} /> Primary
                  </span>
                )}
              </div>
              <span className="text-[11px] text-textTertiary">
                Auto-fallback: 3.5 → 3.1 → 2.5
              </span>
            </div>
          </div>

          <button
            onClick={() => setSidebarOpen(false)}
            className="p-1.5 rounded-full hover:bg-gray-100 text-textSecondary transition-colors flex-shrink-0"
          >
            <X size={18} />
          </button>
        </div>

        {/* Fallback Notice Alert Banner */}
        {fallbackNotice && (
          <div className="bg-amber-50 border-b border-amber-200 px-4 py-2.5 flex items-start gap-2.5 text-xs text-amber-900 animate-fadeIn">
            <AlertTriangle size={16} className="text-amber-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="font-semibold text-amber-950">
                {fallbackNotice.failedModel} is busy ({fallbackNotice.reason})
              </div>
              <div className="text-amber-800 text-[11px] mt-0.5">
                Switched to <span className="font-semibold text-amber-950">{fallbackNotice.fallbackModel}</span> automatically.
              </div>
            </div>
            <button
              onClick={() => setFallbackNotice(null)}
              className="text-amber-700 hover:text-amber-900 p-0.5"
            >
              <X size={13} />
            </button>
          </div>
        )}

        {/* Chat Messages */}
        <div className="flex-1 overflow-y-auto p-5 flex flex-col gap-5">
          {chatMessages.length === 0 && (
            <div className="flex-1 flex flex-col items-center justify-center text-center text-textTertiary py-12">
              <Sparkles size={32} className="mb-3 text-accent opacity-50" />
              <p className="text-sm font-medium text-textPrimary mb-1">Cognitive Canvas Agent</p>
              <p className="text-xs text-textSecondary max-w-xs leading-relaxed">
                Describe any goal, study topic, or exam. If high-tier models exhaust quota or experience high traffic, it automatically cascades to fallback models.
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
            ) : msg.isError ? (
              <div key={i} className="self-start max-w-[95%] w-full">
                <div className="bg-red-50 border border-red-200 rounded-2xl rounded-bl-md p-4 text-xs text-red-900 shadow-sm flex items-start gap-3">
                  <AlertTriangle size={18} className="text-red-600 flex-shrink-0 mt-0.5" />
                  <div className="flex-1 space-y-1">
                    <p className="font-semibold text-red-950">Service Notice</p>
                    <p className="leading-relaxed text-red-800">{msg.text}</p>
                    <p className="text-[11px] text-red-700 font-medium pt-1">
                      💡 Tip: Model traffic spikes are temporary. Try sending your message again.
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <div key={i} className="self-start max-w-[92%] flex flex-col gap-1">
                <div className="bg-surface border border-borderLight px-4 py-3 rounded-2xl rounded-bl-md text-sm leading-relaxed text-textPrimary whitespace-pre-line shadow-sm">
                  {msg.text}
                </div>
                {msg.model && (
                  <div className="flex items-center gap-1 text-[11px] text-textTertiary px-1">
                    <span>Generated by {msg.model}</span>
                    {msg.isFallback && (
                      <span className="text-amber-700 font-medium">(via fallback)</span>
                    )}
                  </div>
                )}
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

        {/* Chat Input */}
        <div className="p-4 border-t border-borderLight flex-shrink-0">
          <div className="flex items-center bg-surface rounded-full px-4 py-1 border border-borderLight focus-within:border-borderFocus transition-colors">
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleChatSend()}
              placeholder="Reply to Agent..."
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
function Dashboard({ projects, isLoading, onRefresh, onSelectProject, onDeleteProject }) {
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
            <ProjectCard
              key={p.id}
              project={p}
              onClick={() => onSelectProject(p)}
              onDelete={(e) => {
                e.stopPropagation();
                if (window.confirm(`Delete project "${p.title}" and all its tasks?`)) {
                  onDeleteProject(p.id);
                }
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ProjectCard({ project, onClick, onDelete }) {
  const isCompleted = project.status === 'completed' || (project.taskCount > 0 && project.completedCount === project.taskCount);

  return (
    <div
      onClick={onClick}
      className="bg-surfaceCard rounded-card border border-borderLight p-5 cursor-pointer shadow-card hover:shadow-cardHover transition-shadow duration-200 flex flex-col justify-between group"
    >
      <div>
        <div className="flex items-center justify-between gap-2 mb-3">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 bg-tagBg text-tagText text-xs font-medium px-2.5 py-1 rounded-full">
              📋 Project
            </span>
            {isCompleted && (
              <span className="inline-flex items-center gap-1 bg-successBg text-successText text-xs font-medium px-2.5 py-1 rounded-full">
                ✓ Completed
              </span>
            )}
          </div>
          <button
            onClick={onDelete}
            title="Delete Project"
            className="opacity-0 group-hover:opacity-100 p-1.5 rounded-full text-textTertiary hover:text-red-600 hover:bg-red-50 transition-all"
          >
            <Trash2 size={15} />
          </button>
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
function ProjectDetail({ projectId, onBack, onDeleteProject, onDeleteTask }) {
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

  const handleTaskDelete = async (e, taskId) => {
    e.stopPropagation();
    try {
      await onDeleteTask(taskId);
      setProject((prev) => ({
        ...prev,
        tasks: prev.tasks.filter((t) => t.id !== taskId),
      }));
    } catch (err) {
      console.error('Failed to delete task:', err);
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
      <div className="flex items-center justify-between mb-5">
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 text-sm text-textSecondary hover:text-accentText font-medium transition-colors"
        >
          <ChevronLeft size={16} /> Back to Projects
        </button>
        <button
          onClick={() => {
            if (window.confirm(`Are you sure you want to delete "${project.title}" and all its tasks?`)) {
              onDeleteProject(project.id);
            }
          }}
          className="flex items-center gap-1.5 text-xs font-medium text-red-600 hover:text-red-700 bg-red-50 hover:bg-red-100 px-3 py-1.5 rounded-full transition-colors"
        >
          <Trash2 size={13} />
          Delete Project
        </button>
      </div>

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
                    "flex items-center gap-3 bg-surfaceCard rounded-card border border-borderLight px-5 py-3.5 transition-all hover:shadow-card cursor-pointer select-none group",
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
                  <button
                    onClick={(e) => handleTaskDelete(e, task.id)}
                    title="Delete Task"
                    className="opacity-0 group-hover:opacity-100 p-1.5 rounded-full text-textTertiary hover:text-red-600 hover:bg-red-50 transition-all"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── 1-Year Scrollable Calendar & Dynamic Schedule ──────────────
function CalendarView({ tasks, isLoading, onToggleTask, onCreateTask, onDeleteTask }) {
  // Current local date (August 30, 2026)
  const todayISO = '2026-08-30';
  const [selectedDate, setSelectedDate] = useState(todayISO);
  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [isCreatingTask, setIsCreatingTask] = useState(false);
  const calendarScrollRef = useRef(null);

  // Generate 12 months (1 full year) starting from current month (Aug 2026 to Jul 2027)
  const yearMonths = useMemo(() => {
    const months = [];
    const baseDate = new Date(2026, 7, 1); // August 2026
    const startYear = baseDate.getFullYear();
    const startMonth = baseDate.getMonth();

    for (let i = 0; i < 12; i++) {
      const d = new Date(startYear, startMonth + i, 1);
      const year = d.getFullYear();
      const month = d.getMonth();
      const monthName = d.toLocaleString('en-US', { month: 'long' });
      const daysInMonth = new Date(year, month + 1, 0).getDate();
      
      // Monday = 0, Sunday = 6
      let firstDayIndex = d.getDay() - 1;
      if (firstDayIndex === -1) firstDayIndex = 6;

      months.push({
        year,
        month,
        monthName,
        daysInMonth,
        firstDayIndex,
        key: `${year}-${month}`,
      });
    }
    return months;
  }, []);

  const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

  // Map task counts per day string (YYYY-MM-DD)
  const tasksByDate = useMemo(() => {
    const map = {};
    for (const t of tasks) {
      if (t.dueDate) {
        map[t.dueDate] = map[t.dueDate] || { total: 0, done: 0 };
        map[t.dueDate].total += 1;
        if (t.done) map[t.dueDate].done += 1;
      }
    }
    // Also attach unassigned active tasks to Today's date
    const unassignedTasks = tasks.filter((t) => !t.dueDate);
    if (unassignedTasks.length > 0) {
      map[todayISO] = map[todayISO] || { total: 0, done: 0 };
      map[todayISO].total += unassignedTasks.length;
      map[todayISO].done += unassignedTasks.filter((t) => t.done).length;
    }
    return map;
  }, [tasks, todayISO]);

  // Filter tasks for the selected date
  const filteredTasks = useMemo(() => {
    if (selectedDate === todayISO) {
      // For Today: show tasks explicitly due today + unassigned tasks
      return tasks.filter((t) => t.dueDate === todayISO || !t.dueDate);
    } else {
      // For any other date: show tasks scheduled for this date
      return tasks.filter((t) => t.dueDate === selectedDate);
    }
  }, [tasks, selectedDate, todayISO]);

  // Formatted date label for header
  const formattedSelectedDate = useMemo(() => {
    const [y, m, d] = selectedDate.split('-').map(Number);
    const dateObj = new Date(y, m - 1, d);
    const dateStr = dateObj.toLocaleDateString('en-US', {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    });
    return selectedDate === todayISO ? `${dateStr} (Today)` : dateStr;
  }, [selectedDate, todayISO]);

  const handleQuickAddTask = async (e) => {
    e.preventDefault();
    if (!newTaskTitle.trim()) return;
    setIsCreatingTask(true);
    try {
      await onCreateTask({
        title: newTaskTitle.trim(),
        dueDate: selectedDate,
        priority: 'medium',
        taskType: 'task',
      });
      setNewTaskTitle('');
    } finally {
      setIsCreatingTask(false);
    }
  };

  const jumpToToday = () => {
    setSelectedDate(todayISO);
    calendarScrollRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="flex flex-col lg:flex-row gap-8">
      {/* ── Left Column: 1-Year Scrollable Calendar ── */}
      <div className="w-full lg:w-5/12 flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-semibold text-textPrimary">Calendar</h1>
            <p className="text-xs text-textSecondary mt-0.5">1-Year Horizon (Aug 2026 – Jul 2027)</p>
          </div>
          <button
            onClick={jumpToToday}
            className="flex items-center gap-1.5 text-xs font-medium bg-accentLight text-accentText px-3 py-1.5 rounded-full hover:bg-blue-100 transition-colors shadow-sm"
          >
            <CalendarIcon size={13} />
            Today
          </button>
        </div>

        {/* Scrollable Month List */}
        <div
          ref={calendarScrollRef}
          className="bg-surfaceCard rounded-card border border-borderLight p-4 shadow-card max-h-[640px] overflow-y-auto space-y-6"
        >
          {yearMonths.map((m) => (
            <div key={m.key} className="pb-4 border-b border-borderLight last:border-b-0 last:pb-0">
              <div className="flex items-center justify-between mb-3 px-1">
                <h3 className="font-semibold text-sm text-textPrimary">
                  {m.monthName} <span className="text-textTertiary font-normal">{m.year}</span>
                </h3>
              </div>

              {/* Day of Week Headers */}
              <div className="grid grid-cols-7 mb-2">
                {dayNames.map((d) => (
                  <div key={d} className="text-center text-[11px] font-medium text-textTertiary py-1">
                    {d}
                  </div>
                ))}
              </div>

              {/* Month Days Grid */}
              <div className="grid grid-cols-7 gap-y-1.5">
                {/* Empty cells before 1st of month */}
                {Array.from({ length: m.firstDayIndex }).map((_, i) => (
                  <div key={`empty-${i}`} />
                ))}

                {/* Days of Month */}
                {Array.from({ length: m.daysInMonth }).map((_, i) => {
                  const dayNum = i + 1;
                  const dayStr = String(dayNum).padStart(2, '0');
                  const monthStr = String(m.month + 1).padStart(2, '0');
                  const dateISO = `${m.year}-${monthStr}-${dayStr}`;

                  const isSelected = dateISO === selectedDate;
                  const isToday = dateISO === todayISO;
                  const dayStats = tasksByDate[dateISO];
                  const hasTasks = dayStats && dayStats.total > 0;
                  const allDone = hasTasks && dayStats.done === dayStats.total;

                  return (
                    <button
                      key={dateISO}
                      onClick={() => setSelectedDate(dateISO)}
                      className={cn(
                        "w-9 h-9 mx-auto rounded-full flex flex-col items-center justify-center text-xs font-medium relative transition-all",
                        isSelected
                          ? "bg-accent text-white shadow-sm font-semibold scale-105"
                          : isToday
                          ? "bg-accentLight text-accentText font-bold border border-accent"
                          : "text-textPrimary hover:bg-gray-100"
                      )}
                    >
                      <span>{dayNum}</span>

                      {/* Task Indicator Dot */}
                      {hasTasks && !isSelected && (
                        <span
                          className={cn(
                            "absolute bottom-1 w-1.5 h-1.5 rounded-full",
                            allDone ? "bg-emerald-500" : "bg-accent"
                          )}
                          title={`${dayStats.done}/${dayStats.total} tasks completed`}
                        />
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Right Column: Filtered Schedule by Selected Date ── */}
      <div className="w-full lg:w-7/12 flex flex-col">
        <div className="flex items-baseline justify-between mb-4">
          <div>
            <h2 className="text-2xl font-semibold text-textPrimary">{formattedSelectedDate}</h2>
            <p className="text-sm text-textSecondary mt-0.5">
              {filteredTasks.length === 0
                ? 'No tasks scheduled'
                : `${filteredTasks.length} ${filteredTasks.length === 1 ? 'task' : 'tasks'} for this date`}
            </p>
          </div>
        </div>

        {/* Schedule List */}
        <div className="flex-1 flex flex-col">
          {isLoading ? (
            <div className="bg-surfaceCard rounded-card border border-borderLight p-12 text-center shadow-card">
              <Loader2 size={28} className="animate-spin text-accent mx-auto mb-2" />
              <p className="text-sm text-textTertiary">Loading schedule from Firestore...</p>
            </div>
          ) : filteredTasks.length === 0 ? (
            <div className="bg-surfaceCard rounded-card border border-borderLight p-10 text-center shadow-card mb-4">
              <CalendarDays size={36} className="text-accent mx-auto mb-3 opacity-60" />
              <h3 className="text-base font-medium text-textPrimary mb-1">No Tasks for this Date</h3>
              <p className="text-xs text-textSecondary max-w-sm mx-auto">
                {selectedDate < todayISO
                  ? 'No past tasks were recorded for this day.'
                  : 'Add a new task below or ask the AI agent to schedule learning plans on this date.'}
              </p>
            </div>
          ) : (
            <div className="space-y-3 mb-4">
              {filteredTasks.map((item, i) => (
                <div
                  key={item.id}
                  onClick={() => onToggleTask(item.id, item.done)}
                  className={cn(
                    "flex items-center gap-3.5 bg-surfaceCard rounded-card border border-borderLight px-5 py-4 transition-all hover:shadow-card cursor-pointer select-none group",
                    item.done && "bg-surface opacity-75"
                  )}
                >
                  <span className="text-sm text-textTertiary font-medium w-5 text-center flex-shrink-0">
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

                  {item.priority && (
                    <span className={cn(
                      "text-[10px] uppercase font-semibold px-2 py-0.5 rounded-full",
                      item.priority === 'high' ? "bg-red-50 text-red-700 border border-red-200" :
                      item.priority === 'medium' ? "bg-amber-50 text-amber-700 border border-amber-200" :
                      "bg-gray-100 text-gray-700 border border-gray-200"
                    )}>
                      {item.priority}
                    </span>
                  )}

                  {item.estimatedMinutes && (
                    <span className="text-xs text-textTertiary bg-tagBg px-2 py-0.5 rounded">
                      {item.estimatedMinutes}m
                    </span>
                  )}

                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteTask(item.id);
                    }}
                    title="Delete Task"
                    className="opacity-0 group-hover:opacity-100 p-1.5 rounded-full text-textTertiary hover:text-red-600 hover:bg-red-50 transition-all"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Quick Add Task directly on selected date */}
          <form onSubmit={handleQuickAddTask} className="mt-auto pt-2">
            <div className="flex items-center bg-white border border-borderLight rounded-full shadow-card px-4 py-1 focus-within:border-borderFocus focus-within:shadow-cardHover transition-all">
              <Plus size={18} className="text-accent mr-2 flex-shrink-0" />
              <input
                type="text"
                value={newTaskTitle}
                onChange={(e) => setNewTaskTitle(e.target.value)}
                placeholder={`Add task for ${formattedSelectedDate.split('(')[0].trim()}...`}
                className="flex-1 py-2.5 text-sm bg-transparent outline-none placeholder:text-textTertiary"
                disabled={isCreatingTask}
              />
              <button
                type="submit"
                disabled={!newTaskTitle.trim() || isCreatingTask}
                className="ml-2 text-xs font-semibold bg-accent text-white px-3.5 py-1.5 rounded-full hover:bg-accentHover transition-colors disabled:opacity-50"
              >
                {isCreatingTask ? 'Adding...' : 'Add'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

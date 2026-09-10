import { useState } from 'react';
import type { MouseEvent as ReactMouseEvent, RefObject } from 'react';
import type { Projekt, ProjektyNode, ProjectGroup } from '../../../types';
import {
  ChevronDownIcon,
  CheckIcon,
  PencilIcon,
  TrashIcon,
  PlusIcon,
} from '../icons/CanvasIcons';

interface CanvasHeaderProps {
  theme?: 'light' | 'dark';
  isMacroView: boolean;
  activeProject?: Projekt;
  projects: Projekt[];
  groups: ProjectGroup[];
  activeProjectId: string;
  isProjectMenuOpen: boolean;
  setIsProjectMenuOpen: React.Dispatch<React.SetStateAction<boolean>>;
  projectMenuRef: RefObject<HTMLDivElement | null>;
  editingProjectId: string | null;
  editingProjectName: string;
  setEditingProjectId: (id: string | null) => void;
  setEditingProjectName: (name: string) => void;
  handleSwitchProject: (id: string) => void | Promise<void>;
  handleCreateProject: (targetGroupId?: string | null) => void | Promise<void>;
  handleStartRename: (proj: Projekt, e: ReactMouseEvent) => void;
  handleSaveRename: (id: string) => void | Promise<void>;
  handleDeleteProject: (id: string, e: ReactMouseEvent) => void | Promise<void>;
  onToggleGroupCollapse: (groupId: string) => void;
  onCreateGroup: (name: string) => void;
  onDeleteGroup: (groupId: string, mode: 'move_to_root' | 'delete_all') => void;
  onMoveProject: (projectId: string, targetGroupId: string | null) => void;
  zoomToMacroView: () => void;
  boardPath: string[];
  breadcrumbNodes: ProjektyNode[];
  goToBoardLevel: (index: number) => void;
  parentId: string | null;
  zoomBy: (factor: number) => void;
  resetView: () => void;
  scale: number;
  toggleTheme?: () => void;
  showHelp: boolean;
  setShowHelp: React.Dispatch<React.SetStateAction<boolean>>;
  liveTrackingEnabled: boolean;
  setLiveTrackingEnabled: React.Dispatch<React.SetStateAction<boolean>>;
}

export function CanvasHeader({
  theme,
  isMacroView,
  activeProject,
  projects,
  groups,
  activeProjectId,
  isProjectMenuOpen,
  setIsProjectMenuOpen,
  projectMenuRef,
  editingProjectId,
  editingProjectName,
  setEditingProjectId,
  setEditingProjectName,
  handleSwitchProject,
  handleCreateProject,
  handleStartRename,
  handleSaveRename,
  handleDeleteProject,
  onToggleGroupCollapse,
  onCreateGroup,
  onDeleteGroup,
  onMoveProject,
  zoomToMacroView,
  boardPath,
  breadcrumbNodes,
  goToBoardLevel,
  parentId,
  zoomBy,
  resetView,
  scale,
  toggleTheme,
  showHelp,
  setShowHelp,
  liveTrackingEnabled,
  setLiveTrackingEnabled,
}: CanvasHeaderProps) {
  // Stan modali wewnątrz nagłówka
  const [isNewGroupModalOpen, setIsNewGroupModalOpen] = useState(false);
  const [newGroupName, setNewGroupName] = useState('');

  const [moveModalProjectId, setMoveModalProjectId] = useState<string | null>(null);

  const [deleteGroupModalId, setDeleteGroupModalId] = useState<string | null>(null);

  const handleOpenCreateGroup = (e: ReactMouseEvent) => {
    e.stopPropagation();
    setNewGroupName('');
    setIsNewGroupModalOpen(true);
  };

  const handleConfirmCreateGroup = () => {
    const trimmed = newGroupName.trim();
    if (trimmed) {
      onCreateGroup(trimmed);
    }
    setIsNewGroupModalOpen(false);
    setNewGroupName('');
  };

  const unassignedProjects = projects.filter((p) => !p.folder_id);

  return (
    <>
      <header
        className="absolute top-3 left-1/2 -translate-x-1/2 z-20 flex items-center gap-2 px-3.5 h-10 rounded-2xl border backdrop-blur-2xl transition-all duration-200 shadow-sm"
        style={{
          backgroundColor: theme === 'dark' ? 'rgba(20, 20, 20, 0.95)' : 'rgba(255, 255, 255, 0.88)',
          borderColor: theme === 'dark' ? '#262626' : 'rgba(226, 232, 240, 0.9)',
          boxShadow: theme === 'dark' ? '0 12px 32px rgba(0, 0, 0, 0.6)' : '0 4px 20px -2px rgba(0, 0, 0, 0.06)',
        }}
      >
        <div className="flex items-center gap-2">
          {/* Nazwa aplikacji */}
          <span className={`text-xs font-bold tracking-tight select-none ${theme === 'dark' ? 'text-white' : 'text-slate-800'}`}>
            Cortex
          </span>
          <span className={theme === 'dark' ? 'text-[#444]' : 'text-slate-300'}>:</span>

          {/* Przełącznik Projektów / Tablic */}
          <div className="relative" ref={projectMenuRef}>
            <button
              tabIndex={-1}
              data-testid="project-switcher-button"
              onClick={() => {
                setIsProjectMenuOpen((prev) => !prev);
                setEditingProjectId(null);
              }}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium cursor-pointer transition-all ${
                isProjectMenuOpen
                  ? theme === 'dark'
                    ? 'bg-[#222222] text-white border border-[#333333] shadow-sm'
                    : 'bg-slate-200/90 text-slate-900 border border-slate-300 shadow-sm'
                  : theme === 'dark'
                  ? 'bg-[#181818] hover:bg-[#202020] text-[#dddddd] border border-[#262626]'
                  : 'hover:bg-slate-100 text-slate-700 hover:text-slate-900 border border-slate-200'
              }`}
              title="Wybierz lub zarządzaj tablicami projektów"
            >
              <span className="max-w-[170px] truncate flex items-center gap-1.5">
                {isMacroView ? (
                  <span>Wszystkie projekty</span>
                ) : (
                  activeProject?.name || 'Tablica główna'
                )}
              </span>
              <ChevronDownIcon className={`w-3.5 h-3.5 transition-transform duration-200 ${isProjectMenuOpen ? 'rotate-180 text-white' : 'text-[#777]'}`} />
            </button>

            {/* Menu rozwijane projektów */}
            {isProjectMenuOpen && (
              <div
                data-testid="project-dropdown-menu"
                className={`absolute top-full left-0 mt-2 w-80 rounded-2xl border shadow-2xl backdrop-blur-xl z-50 overflow-hidden flex flex-col p-2 animate-in fade-in zoom-in-95 duration-150 ${
                  theme === 'dark'
                    ? 'bg-[#141414] border-[#282828] text-[#cccccc]'
                    : 'bg-white/95 border-slate-200 text-slate-800'
                }`}
              >
                {/* Przycisk widoku makro */}
                <div className="pb-1.5 border-b border-[#222222] dark:border-[#222222]">
                  <button
                    data-testid="macro-view-toggle-btn"
                    onClick={() => {
                      setIsProjectMenuOpen(false);
                      zoomToMacroView();
                    }}
                    className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs font-medium cursor-pointer transition-colors ${
                      isMacroView
                        ? theme === 'dark' ? 'bg-[#222222] text-white font-semibold' : 'bg-slate-800 text-white font-semibold'
                        : theme === 'dark' ? 'hover:bg-[#1a1a1a] text-[#aaaaaa]' : 'hover:bg-slate-100 text-slate-600'
                    }`}
                  >
                    <span>Widok wszystkich projektów</span>
                    <span className="text-[10px] opacity-60 font-mono">Oddalenie &lt; 15%</span>
                  </button>
                </div>

                {/* Nagłówek sekcji tablic + przycisk +Folder */}
                <div className="px-2 pt-2 pb-1 text-[11px] font-medium tracking-wider uppercase text-[#777777] flex items-center justify-between">
                  <span>Twoje tablice ({projects.length})</span>
                  <button
                    onClick={handleOpenCreateGroup}
                    className="text-[10px] px-2 py-0.5 rounded text-[#FFC799] hover:bg-[rgba(255,199,153,0.1)] transition-colors cursor-pointer font-medium"
                    title="Utwórz nowy folder grupujący"
                  >
                    + Folder
                  </button>
                </div>

                {/* Lista folderów i tablic */}
                <div className="max-h-72 overflow-y-auto space-y-1.5 py-1 pr-0.5">
                  
                  {/* 1. Foldery (Grupy) */}
                  {groups.map((group) => {
                    const groupProjects = projects.filter((p) => p.folder_id === group.id);
                    return (
                      <div
                        key={group.id}
                        className="rounded-xl border border-[#222222] bg-[#101010] overflow-hidden group/folder"
                      >
                        {/* Nagłówek folderu */}
                        <div className="flex items-center justify-between px-2.5 py-1.5 hover:bg-[#181818] transition-colors">
                          <div
                            onClick={() => onToggleGroupCollapse(group.id)}
                            className="flex items-center gap-2 cursor-pointer flex-1 min-w-0"
                          >
                            <svg
                              className={`w-3 h-3 text-[#777] transition-transform ${group.collapsed ? '-rotate-90' : ''}`}
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="2"
                            >
                              <path d="m6 9 6 6 6-6" />
                            </svg>
                            <span className="font-medium text-[#dddddd] text-xs truncate">{group.name}</span>
                            <span className="text-[10px] text-[#666666] font-mono">({groupProjects.length})</span>
                          </div>

                          {/* Akcje folderu */}
                          <div className="flex items-center gap-1 opacity-0 group-hover/folder:opacity-100 transition-opacity">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                void handleCreateProject(group.id);
                              }}
                              className="p-1 rounded hover:bg-[#282828] text-[#999] hover:text-white"
                              title="Dodaj tablicę do tego folderu"
                            >
                              <PlusIcon className="w-3 h-3" />
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setDeleteGroupModalId(group.id);
                              }}
                              className="p-1 rounded hover:bg-[#282828] text-[#999] hover:text-[#ff8080]"
                              title="Usuń folder"
                            >
                              <TrashIcon className="w-3 h-3" />
                            </button>
                          </div>
                        </div>

                        {/* Zawartość folderu */}
                        {!group.collapsed && (
                          <div className="pl-3 pr-1 py-1 flex flex-col gap-0.5 border-t border-[#1a1a1a] bg-[#141414]">
                            {groupProjects.length > 0 ? (
                              groupProjects.map((proj) => {
                                const isActive = proj.id === activeProjectId;
                                const isEditingThis = editingProjectId === proj.id;

                                if (isEditingThis) {
                                  return (
                                    <div
                                      key={proj.id}
                                      className="flex items-center gap-1 px-2 py-1 rounded-lg bg-[#222222] border border-[#333333]"
                                      onClick={(e) => e.stopPropagation()}
                                    >
                                      <input
                                        type="text"
                                        autoFocus
                                        value={editingProjectName}
                                        onChange={(e) => setEditingProjectName(e.target.value)}
                                        onKeyDown={(e) => {
                                          if (e.key === 'Enter') handleSaveRename(proj.id);
                                          if (e.key === 'Escape') setEditingProjectId(null);
                                        }}
                                        className="flex-1 text-xs bg-transparent border-none outline-none font-medium px-1 text-white"
                                        placeholder="Nazwa tablicy..."
                                      />
                                      <button
                                        onClick={() => handleSaveRename(proj.id)}
                                        className="p-1 rounded hover:bg-[#2e2e2e] text-[#cccccc] cursor-pointer"
                                        title="Zapisz nazwę"
                                      >
                                        <CheckIcon className="w-3.5 h-3.5" />
                                      </button>
                                    </div>
                                  );
                                }

                                return (
                                  <div
                                    key={proj.id}
                                    data-testid={`project-item-${proj.id}`}
                                    onClick={() => handleSwitchProject(proj.id)}
                                    className={`group flex items-center justify-between px-2 py-1.5 rounded-lg text-xs cursor-pointer transition-colors ${
                                      isActive
                                        ? 'bg-[#222222] text-white font-medium shadow-sm'
                                        : 'hover:bg-[#1a1a1a] text-[#aaaaaa]'
                                    }`}
                                  >
                                    <div className="flex items-center gap-2 truncate">
                                      <span className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-[#FFC799]' : 'bg-transparent'}`} />
                                      <span className="truncate">{proj.name}</span>
                                    </div>

                                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                      <button
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          setMoveModalProjectId(proj.id);
                                        }}
                                        className="p-1 rounded hover:bg-[#2e2e2e] text-[#888] hover:text-white"
                                        title="Przenieś tablicę do innego folderu"
                                      >
                                        ⇄
                                      </button>
                                      <button
                                        data-testid={`project-rename-${proj.id}`}
                                        onClick={(e) => handleStartRename(proj, e)}
                                        className="p-1 rounded hover:bg-[#2e2e2e] text-[#888] hover:text-white transition-colors"
                                        title="Zmień nazwę"
                                      >
                                        <PencilIcon className="w-3 h-3" />
                                      </button>
                                      {projects.length > 1 && (
                                        <button
                                          data-testid={`project-delete-${proj.id}`}
                                          onClick={(e) => handleDeleteProject(proj.id, e)}
                                          className="p-1 rounded hover:bg-[#2e2e2e] text-[#888] hover:text-[#ff8080] transition-colors"
                                          title="Usuń tablicę"
                                        >
                                          <TrashIcon className="w-3 h-3" />
                                        </button>
                                      )}
                                    </div>
                                  </div>
                                );
                              })
                            ) : (
                              <div className="px-2 py-1.5 text-[10px] text-[#555] italic flex items-center justify-between">
                                <span>Pusty folder</span>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    void handleCreateProject(group.id);
                                  }}
                                  className="text-[#FFC799] hover:underline font-medium"
                                >
                                  + Dodaj
                                </button>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}

                  {/* 2. Luźne tablice (Pozostałe tablice) */}
                  <div className="pt-1">
                    <div className="px-2 py-1 text-[10px] font-medium text-[#666666] uppercase tracking-wider flex items-center justify-between">
                      <span>Pozostałe tablice ({unassignedProjects.length})</span>
                    </div>

                    <div className="space-y-0.5 mt-0.5">
                      {unassignedProjects.map((proj) => {
                        const isActive = proj.id === activeProjectId;
                        const isEditingThis = editingProjectId === proj.id;

                        if (isEditingThis) {
                          return (
                            <div
                              key={proj.id}
                              className="flex items-center gap-1 px-2 py-1 rounded-lg bg-[#222222] border border-[#333333]"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <input
                                type="text"
                                autoFocus
                                value={editingProjectName}
                                onChange={(e) => setEditingProjectName(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') handleSaveRename(proj.id);
                                  if (e.key === 'Escape') setEditingProjectId(null);
                                }}
                                className="flex-1 text-xs bg-transparent border-none outline-none font-medium px-1 text-white"
                                placeholder="Nazwa tablicy..."
                              />
                              <button
                                onClick={() => handleSaveRename(proj.id)}
                                className="p-1 rounded hover:bg-[#2e2e2e] text-[#cccccc] cursor-pointer"
                                title="Zapisz nazwę"
                              >
                                <CheckIcon className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          );
                        }

                        return (
                          <div
                            key={proj.id}
                            data-testid={`project-item-${proj.id}`}
                            onClick={() => handleSwitchProject(proj.id)}
                            className={`group flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs cursor-pointer transition-colors border ${
                              isActive
                                ? 'bg-[#222222] border-[#333333] text-white font-medium shadow-sm'
                                : 'bg-[#101010] border-[#1c1c1c] hover:bg-[#181818] text-[#aaaaaa]'
                            }`}
                          >
                            <div className="flex items-center gap-2 truncate">
                              <span className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-[#FFC799]' : 'bg-[#444444]'}`} />
                              <span className="truncate">{proj.name}</span>
                            </div>

                            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setMoveModalProjectId(proj.id);
                                }}
                                className="p-1 rounded hover:bg-[#2e2e2e] text-[#888] hover:text-white"
                                title="Przenieś tablicę do folderu"
                              >
                                ⇄
                              </button>
                              <button
                                data-testid={`project-rename-${proj.id}`}
                                onClick={(e) => handleStartRename(proj, e)}
                                className="p-1 rounded hover:bg-[#2e2e2e] text-[#888] hover:text-white transition-colors"
                                title="Zmień nazwę"
                              >
                                <PencilIcon className="w-3 h-3" />
                              </button>
                              {projects.length > 1 && (
                                <button
                                  data-testid={`project-delete-${proj.id}`}
                                  onClick={(e) => handleDeleteProject(proj.id, e)}
                                  className="p-1 rounded hover:bg-[#2e2e2e] text-[#888] hover:text-[#ff8080] transition-colors"
                                  title="Usuń tablicę"
                                >
                                  <TrashIcon className="w-3 h-3" />
                                </button>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                </div>

                {/* Dolny pasek tworzenia tablicy */}
                <div className="pt-1.5 border-t border-[#222222] flex gap-1.5">
                  <button
                    data-testid="project-create-button"
                    onClick={() => handleCreateProject(null)}
                    className="flex-1 py-1.5 px-3 rounded-lg bg-[#202020] hover:bg-[#282828] text-[#eeeeee] font-medium text-xs flex items-center justify-center gap-1.5 cursor-pointer transition-colors border border-[#2a2a2a]"
                  >
                    <PlusIcon className="w-3 h-3" />
                    <span>Nowa tablica</span>
                  </button>
                  <button
                    onClick={handleOpenCreateGroup}
                    className="py-1.5 px-3 rounded-lg bg-[#181818] hover:bg-[#222222] border border-[#282828] text-[#FFC799] font-medium text-xs flex items-center justify-center cursor-pointer transition-colors"
                  >
                    <span>+ Folder</span>
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Okruszki pod-tablic (F2 drill down w ramach wybranego projektu) */}
          {boardPath.length > 0 && (
            <nav className="flex items-center gap-1 text-xs" aria-label="Nawigacja pod-tablic">
              <button
                tabIndex={-1}
                onClick={() => goToBoardLevel(-1)}
                className={`px-1.5 py-0.5 rounded-md cursor-pointer transition-colors ${
                  parentId === null
                    ? theme === 'dark'
                      ? 'text-white font-medium bg-[#222222]'
                      : 'text-slate-800 font-medium bg-slate-100'
                    : theme === 'dark'
                    ? 'text-[#888] hover:bg-[#1e1e1e] hover:text-white'
                    : 'text-slate-500 hover:bg-slate-100 hover:text-slate-700'
                }`}
              >
                Root
              </button>
              {breadcrumbNodes.map((node, i) => (
                <span key={node.id} className="flex items-center gap-1">
                  <span className={theme === 'dark' ? 'text-[#555]' : 'text-slate-300'}>/</span>
                  <button
                    tabIndex={-1}
                    onClick={() => goToBoardLevel(i)}
                    className={`max-w-[100px] truncate px-1.5 py-0.5 rounded-md cursor-pointer transition-colors ${
                      i === boardPath.length - 1
                        ? theme === 'dark'
                          ? 'text-white font-medium bg-[#222222]'
                          : 'text-slate-800 font-medium bg-slate-100'
                        : theme === 'dark'
                        ? 'text-[#888] hover:bg-[#1e1e1e] hover:text-white'
                        : 'text-slate-500 hover:bg-slate-100 hover:text-slate-700'
                    }`}
                  >
                    {node.title || 'Bez tytułu'}
                  </button>
                </span>
              ))}
            </nav>
          )}
        </div>

        <div className="w-[1px] h-4 bg-[#262626] dark:bg-[#262626] mx-0.5" />

        {/* Kontrolki zoomu, motywu i pomocy */}
        <div className="flex items-center gap-1">
          <button
            tabIndex={-1}
            onClick={() => zoomBy(1 / 1.1)}
            className="w-6 h-6 flex items-center justify-center rounded-md text-xs text-[#888] hover:bg-[#202020] hover:text-white cursor-pointer transition-colors"
            title="Pomniejsz"
          >
            −
          </button>
          <button
            tabIndex={-1}
            onClick={resetView}
            className="h-6 px-1.5 rounded-md text-xs tabular-nums text-[#aaa] hover:bg-[#202020] hover:text-white font-medium cursor-pointer transition-colors"
            title="Przywróć 100%"
          >
            {Math.round(scale * 100)}%
          </button>
          <button
            tabIndex={-1}
            onClick={() => zoomBy(1.1)}
            className="w-6 h-6 flex items-center justify-center rounded-md text-xs text-[#888] hover:bg-[#202020] hover:text-white cursor-pointer transition-colors"
            title="Powiększ"
          >
            +
          </button>

          <div className="w-[1px] h-3.5 bg-[#262626] mx-0.5" />

          <button
            tabIndex={-1}
            onClick={() => setLiveTrackingEnabled((v) => !v)}
            data-testid="live-tracking-toggle"
            className={`w-6 h-6 flex items-center justify-center rounded-md text-xs font-semibold cursor-pointer transition-colors ${
              liveTrackingEnabled
                ? 'bg-[#282828] text-[#FFC799]'
                : 'text-[#888] hover:bg-[#202020] hover:text-white'
            }`}
            title={liveTrackingEnabled ? 'Live tracking aktywny' : 'Live tracking wyłączony'}
          >
            ●
          </button>

          <button
            tabIndex={-1}
            onClick={() => setShowHelp((v) => !v)}
            data-testid="help-toggle"
            className={`w-6 h-6 flex items-center justify-center rounded-md text-xs font-semibold cursor-pointer transition-colors ${
              showHelp
                ? 'bg-[#282828] text-white'
                : 'text-[#888] hover:bg-[#202020] hover:text-white'
            }`}
            title="Skróty klawiszowe (?)"
          >
            ?
          </button>
        </div>
      </header>

      {/* Modal: Tworzenie nowego folderu */}
      {isNewGroupModalOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-100"
          onClick={() => setIsNewGroupModalOpen(false)}
        >
          <div
            className="w-full max-w-sm rounded-xl bg-[#161616] border border-[#2a2a2a] p-5 shadow-2xl space-y-4 text-xs"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-[#242424] pb-2">
              <h3 className="font-semibold text-sm text-white">Nowy Folder</h3>
              <button onClick={() => setIsNewGroupModalOpen(false)} className="text-[#666] hover:text-white cursor-pointer">✕</button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-[#888] text-[11px] mb-1 font-medium">Nazwa folderu:</label>
                <input
                  type="text"
                  autoFocus
                  value={newGroupName}
                  onChange={(e) => setNewGroupName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleConfirmCreateGroup();
                    if (e.key === 'Escape') setIsNewGroupModalOpen(false);
                  }}
                  className="w-full bg-[#101010] border border-[#2a2a2a] rounded-lg px-3 py-1.5 text-white outline-none focus:border-[#FFC799]"
                  placeholder="np. Badania, Oferty, Projekty..."
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  onClick={() => setIsNewGroupModalOpen(false)}
                  className="px-3 py-1 rounded-lg bg-[#202020] text-[#999] hover:bg-[#282828] font-medium cursor-pointer"
                >
                  Anuluj
                </button>
                <button
                  onClick={handleConfirmCreateGroup}
                  className="px-3 py-1 rounded-lg bg-[#FFC799] text-[#101010] font-semibold hover:bg-[#ffd6b3] cursor-pointer"
                >
                  Utwórz
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Przenoszenie tablicy do innego folderu */}
      {moveModalProjectId && (() => {
        const targetProj = projects.find((p) => p.id === moveModalProjectId);
        if (!targetProj) return null;

        return (
          <div
            className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-100"
            onClick={() => setMoveModalProjectId(null)}
          >
            <div
              className="w-full max-w-sm rounded-xl bg-[#161616] border border-[#2a2a2a] p-5 shadow-2xl space-y-4 text-xs"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between border-b border-[#242424] pb-2">
                <h3 className="font-semibold text-sm text-white truncate">Przenieś: {targetProj.name}</h3>
                <button onClick={() => setMoveModalProjectId(null)} className="text-[#666] hover:text-white cursor-pointer">✕</button>
              </div>

              <div className="space-y-1 pt-1">
                <p className="text-[#888] text-xs mb-2">Wybierz miejsce docelowe dla tej tablicy:</p>
                <button
                  onClick={() => {
                    onMoveProject(targetProj.id, null);
                    setMoveModalProjectId(null);
                  }}
                  className={`w-full p-2.5 rounded-lg text-left border cursor-pointer flex items-center justify-between ${
                    targetProj.folder_id == null
                      ? 'bg-[rgba(255,199,153,0.1)] border-[rgba(255,199,153,0.3)] text-white font-medium'
                      : 'bg-[#101010] border-[#222] text-[#999] hover:bg-[#1c1c1c]'
                  }`}
                >
                  <span>Bez folderu (Pozostałe tablice)</span>
                  {targetProj.folder_id == null && <span className="text-[#FFC799] text-[10px]">Obecnie</span>}
                </button>

                {groups.map((g) => (
                  <button
                    key={g.id}
                    onClick={() => {
                      onMoveProject(targetProj.id, g.id);
                      setMoveModalProjectId(null);
                    }}
                    className={`w-full p-2.5 rounded-lg text-left border cursor-pointer flex items-center justify-between ${
                      targetProj.folder_id === g.id
                        ? 'bg-[rgba(255,199,153,0.1)] border-[rgba(255,199,153,0.3)] text-white font-medium'
                        : 'bg-[#101010] border-[#222] text-[#999] hover:bg-[#1c1c1c]'
                    }`}
                  >
                    <span>Folder: {g.name}</span>
                    {targetProj.folder_id === g.id && <span className="text-[#FFC799] text-[10px]">Obecnie</span>}
                  </button>
                ))}
              </div>
            </div>
          </div>
        );
      })()}

      {/* Modal: Bezpieczne usuwanie folderu */}
      {deleteGroupModalId && (() => {
        const groupToDelete = groups.find((g) => g.id === deleteGroupModalId);
        if (!groupToDelete) return null;
        const insideCount = projects.filter((p) => p.folder_id === groupToDelete.id).length;

        return (
          <div
            className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-100"
            onClick={() => setDeleteGroupModalId(null)}
          >
            <div
              className="w-full max-w-md rounded-xl bg-[#161616] border border-[#3a2020] p-5 shadow-2xl space-y-4 text-xs"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center gap-2 text-[#ff8080] font-semibold text-sm border-b border-[#242424] pb-2">
                <span>Usuwanie folderu: {groupToDelete.name}</span>
              </div>
              <p className="text-[#bbbbbb] leading-relaxed">
                Folder zawiera <strong>{insideCount}</strong> {insideCount === 1 ? 'tablicę' : 'tablic'}. Co chcesz zrobić z zawartością?
              </p>
              <div className="flex justify-end gap-2 pt-2 border-t border-[#242424]">
                <button
                  onClick={() => setDeleteGroupModalId(null)}
                  className="px-3 py-1.5 rounded-lg bg-[#202020] text-[#999] hover:bg-[#282828] font-medium cursor-pointer"
                >
                  Anuluj
                </button>
                <button
                  onClick={() => {
                    onDeleteGroup(groupToDelete.id, 'move_to_root');
                    setDeleteGroupModalId(null);
                  }}
                  className="px-3.5 py-1.5 rounded-lg bg-[#2a2a2a] hover:bg-[#333333] text-[#eeeeee] font-medium border border-[#3a3a3a] cursor-pointer"
                >
                  Przenieś tablice do luźnych
                </button>
                <button
                  onClick={() => {
                    onDeleteGroup(groupToDelete.id, 'delete_all');
                    setDeleteGroupModalId(null);
                  }}
                  className="px-3.5 py-1.5 rounded-lg bg-[#d32f2f] hover:bg-[#b71c1c] text-white font-medium cursor-pointer"
                >
                  Usuń wszystko
                </button>
              </div>
            </div>
          </div>
        );
      })()}
    </>
  );
}

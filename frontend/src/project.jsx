import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { api } from "./api";

const ProjectCtx = createContext(null);

export function ProjectProvider({ children }) {
  const [projects, setProjects] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api("/projects/?limit=200")
      .then((list) => {
        setProjects(list);
        if (list.length > 0 && !selectedId) setSelectedId(list[0].id);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const select = useCallback((id) => setSelectedId(id), []);
  const selected = projects.find((p) => p.id === selectedId) || null;

  return (
    <ProjectCtx.Provider value={{ projects, selected, selectedId, select, loading }}>
      {children}
    </ProjectCtx.Provider>
  );
}

export function useProject() {
  return useContext(ProjectCtx);
}

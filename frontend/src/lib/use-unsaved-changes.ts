import { useCallback, useEffect, useRef } from "react";
import { useBeforeUnload, useBlocker, type BlockerFunction } from "react-router-dom";

type PageLocation = { pathname: string; search: string };

export function shouldBlockUnsavedChanges(dirty: boolean, current: PageLocation, next: PageLocation): boolean {
  return dirty && (current.pathname !== next.pathname || current.search !== next.search);
}

export function useUnsavedChanges(dirty: boolean) {
  const dirtyRef = useRef(dirty);
  dirtyRef.current = dirty;
  const blocker = useBlocker(useCallback<BlockerFunction>(({ currentLocation, nextLocation }) =>
    shouldBlockUnsavedChanges(dirtyRef.current, currentLocation, nextLocation), []));

  useEffect(() => {
    if (blocker.state !== "blocked") return;
    if (window.confirm("有尚未保存的修改，离开会丢失这些修改。确定继续吗？")) blocker.proceed();
    else blocker.reset();
  }, [blocker]);

  useBeforeUnload(useCallback((event) => {
    if (!dirtyRef.current) return;
    event.preventDefault();
    event.returnValue = "";
  }, []));

  // A successful, explicitly confirmed deletion invalidates its draft before
  // the caller navigates, without waiting for React's next state render.
  return useCallback(() => { dirtyRef.current = false; }, []);
}

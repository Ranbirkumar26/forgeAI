export interface TaskCard {
  id: string;
  title: string;
  status: "queued" | "running" | "blocked" | "done";
}

export function summarizeTasks(tasks: TaskCard[]) {
  const total = tasks.length;
  const done = tasks.filter((task) => task.status === "done").length;
  const blocked = tasks.filter((task) => task.status === "blocked").length;

  return {
    total,
    done,
    blocked,
    completionRate: total === 0 ? 0 : Math.round((done / total) * 100)
  };
}


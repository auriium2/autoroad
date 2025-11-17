import { EquivalencyManager } from "../CourseSearchTab/EquivalencyManager";

export function EquivalenciesTab() {
  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <div className="p-4">
        <EquivalencyManager />
      </div>
    </div>
  );
}

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface ViewModeSelectorProps {
  value: string;
  onChange: (value: string) => void;
}

export function ViewModeSelector({ value, onChange }: ViewModeSelectorProps) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="w-[140px]">
        <SelectValue placeholder="View mode" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="default">Friendly view</SelectItem>
        <SelectItem value="cost">Nerd view</SelectItem>
      </SelectContent>
    </Select>
  );
}

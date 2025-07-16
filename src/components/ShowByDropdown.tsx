import * as React from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type ShowByOption = "rating" | "hours" | "units";

interface ShowByDropdownProps {
  value: ShowByOption;
  onChange: (value: ShowByOption) => void;
  className?: string;
}

const OPTIONS: { label: string; value: ShowByOption }[] = [
  { label: "Rating", value: "rating" },
  { label: "Hours", value: "hours" },
  { label: "Units", value: "units" },
];

export const ShowByDropdown: React.FC<ShowByDropdownProps> = ({
  value,
  onChange,
  className = "",
}) => {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className={`w-[180] ${className}`}>
        <SelectValue placeholder="Show by" />
      </SelectTrigger>
      <SelectContent>
        {OPTIONS.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            Show by {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
};

export default ShowByDropdown;

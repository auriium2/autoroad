export function graduationYearToPlanningYear(graduationYear: string): string {
  const gradYear = parseInt(graduationYear, 10);
  const freshmanFallYear = gradYear - 4;
  return `${freshmanFallYear}-${freshmanFallYear + 1}`;
}

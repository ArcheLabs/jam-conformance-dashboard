import leaderboardData from '@/data/leaderboard.json';
import { LeaderboardEntry } from '@/types/performance';

const data = leaderboardData as unknown as { teams: LeaderboardEntry[] };

export function getTeamMetadata(teamId: string) {
  const team = data.teams.find(t => t.team_id === teamId);
  if (!team) return {};
  return {
    displayName: team.team_name,
    clientName: team.client_name,
    language: team.language,
    languageColor: team.language_color,
  };
}

export function getTeamByName(teamName: string) {
  return data.teams.find(t =>
    t.team_name.toLowerCase() === teamName.toLowerCase() ||
    t.client_name.toLowerCase() === teamName.toLowerCase()
  );
}

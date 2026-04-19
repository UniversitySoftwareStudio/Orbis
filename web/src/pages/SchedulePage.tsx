import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { CalendarRange, Globe } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../services/api';

interface ScheduleSlot {
  course_code: string;
  course_name: string;
  section_number: string;
  section_type: string;
  instructor_name: string;
  day_of_week: string;
  start_time: string;
  end_time: string;
  location: string;
  is_online: boolean;
}

interface SlotLayout {
  slot: ScheduleSlot;
  columnIndex: number;
  totalColumns: number;
  isConflict: boolean;
}

const DAYS = ['MON', 'TUE', 'WED', 'THU', 'FRI'];
const HOUR_HEIGHT = 80;
const GRID_START = 9;
const GRID_END = 19;
const GRID_HOURS = GRID_END - GRID_START; // 10
const GRID_HEIGHT = GRID_HOURS * HOUR_HEIGHT; // 800

const TODAY_MAP: Record<number, string> = {
  1: 'MON', 2: 'TUE', 3: 'WED', 4: 'THU', 5: 'FRI',
};

function timeToHour(timeStr: string): number {
  const parts = timeStr.split(':');
  return parseInt(parts[0]) + parseInt(parts[1]) / 60;
}

function getCardColor(_sectionType: string): string {
  return 'var(--accent)';
}

function computeDayLayout(daySlots: ScheduleSlot[]): SlotLayout[] {
  if (daySlots.length === 0) return [];

  const sorted = [...daySlots].sort(
    (a, b) => timeToHour(a.start_time) - timeToHour(b.start_time)
  );

  // Build connected components: two slots are connected if their times overlap
  const assignedIndices = new Set<number>();
  const groups: ScheduleSlot[][] = [];

  for (let i = 0; i < sorted.length; i++) {
    if (assignedIndices.has(i)) continue;
    const group: ScheduleSlot[] = [sorted[i]];
    assignedIndices.add(i);

    let changed = true;
    while (changed) {
      changed = false;
      for (let j = 0; j < sorted.length; j++) {
        if (assignedIndices.has(j)) continue;
        const overlapsAny = group.some(
          g =>
            timeToHour(g.start_time) < timeToHour(sorted[j].end_time) &&
            timeToHour(sorted[j].start_time) < timeToHour(g.end_time)
        );
        if (overlapsAny) {
          group.push(sorted[j]);
          assignedIndices.add(j);
          changed = true;
        }
      }
    }
    groups.push(group);
  }

  const result: SlotLayout[] = [];
  for (const group of groups) {
    const isConflict = group.length > 1;
    const totalColumns = group.length;
    group.forEach((slot, columnIndex) => {
      result.push({ slot, columnIndex, totalColumns, isConflict });
    });
  }
  return result;
}

export function SchedulePage() {
  const { user } = useAuth();
  const { t } = useTranslation();
  const [slots, setSlots] = useState<ScheduleSlot[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (user?.userType !== 'student') {
      setLoading(false);
      return;
    }
    api.getMySchedule().then(data => {
      setSlots(data.slots ?? data ?? []);
      setLoading(false);
    }).catch(err => {
      console.error(err);
      setLoading(false);
    });
  }, [user]);

  if (user?.userType !== 'student') {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>
        {t('schedule.notStudent')}
      </div>
    );
  }

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>
        {t('schedule.loading')}
      </div>
    );
  }

  const validSlots = slots.filter(
    s => s && s.day_of_week && s.start_time && s.end_time
  );

  if (validSlots.length === 0) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>
        <h2 style={{ marginBottom: 16, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <CalendarRange size={20} strokeWidth={1.8} />
          {t('schedule.title')}
        </h2>
        {t('schedule.noData')}
      </div>
    );
  }

  const now = new Date();
  const todayKey = TODAY_MAP[now.getDay()] ?? '';
  const currentHour = now.getHours();
  const currentMinute = now.getMinutes();
  const currentTop = (currentHour + currentMinute / 60 - GRID_START) * HOUR_HEIGHT;
  const showTimeLine = currentHour >= GRID_START && currentHour < GRID_END;

  // Group slots by day key
  const slotsByDay: Record<string, ScheduleSlot[]> = {};
  validSlots.forEach(s => {
    const key = s.day_of_week.toUpperCase();
    if (!slotsByDay[key]) slotsByDay[key] = [];
    slotsByDay[key].push(s);
  });

  // Pre-compute layout per day
  const layoutByDay: Record<string, SlotLayout[]> = {};
  DAYS.forEach(day => {
    layoutByDay[day] = computeDayLayout(slotsByDay[day] ?? []);
  });

  return (
    <div style={{ padding: 32 }}>
      <h2 style={{ marginBottom: 24, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <CalendarRange size={20} strokeWidth={1.8} />
        {t('schedule.title')}
      </h2>

      <div style={{
        display: 'flex',
        flexDirection: 'column',
        border: '1px solid var(--border-color)',
        borderRadius: 12,
        overflow: 'hidden',
        boxShadow: 'var(--shadow)',
      }}>

        {/* ── Header row ── */}
        <div style={{ display: 'flex' }}>
          {/* "SAAT" corner above gutter */}
          <div style={{
            width: 60,
            minWidth: 60,
            backgroundColor: 'var(--bg-table-header)',
            color: 'var(--sidebar-text)',
            fontWeight: 'bold',
            textAlign: 'center',
            padding: '10px 4px',
            border: '1px solid #2d3561',
            borderBottom: '3px solid transparent',
            fontSize: 14,
            borderRadius: '8px 0 0 0',
          }}>
            {t('schedule.hour')}
          </div>

          {DAYS.map((day, idx) => (
            <div
              key={day}
              style={{
                flex: 1,
                backgroundColor: 'var(--bg-table-header)',
                color: day === todayKey ? 'var(--accent)' : 'var(--sidebar-text)',
                fontWeight: 'bold',
                textAlign: 'center',
                padding: '10px 4px',
                border: '1px solid #2d3561',
                borderBottom: day === todayKey ? '3px solid var(--accent)' : '3px solid transparent',
                fontSize: 14,
                borderRadius: idx === DAYS.length - 1 ? '0 8px 0 0' : undefined,
              }}
            >
              {t(`schedule.days.${day}`)}
            </div>
          ))}
        </div>

        {/* ── Grid body ── */}
        <div style={{ display: 'flex', position: 'relative' }}>

          {/* Current time indicator — spans all day columns */}
          {showTimeLine && (
            <div style={{
              position: 'absolute',
              top: currentTop,
              left: 60,
              right: 0,
              height: 2,
              backgroundColor: '#f44336',
              zIndex: 10,
              pointerEvents: 'none',
            }}>
              <div style={{
                position: 'absolute',
                left: -5,
                top: -4,
                width: 10,
                height: 10,
                borderRadius: '50%',
                backgroundColor: '#f44336',
              }} />
            </div>
          )}

          {/* Hour gutter */}
          <div style={{
            width: 60,
            minWidth: 60,
            position: 'relative',
            height: GRID_HEIGHT,
            backgroundColor: 'var(--bg-primary)',
            borderRight: '1px solid var(--border-color)',
          }}>
            {Array.from({ length: GRID_HOURS }, (_, i) => i + GRID_START).map(hour => (
              <div key={hour} style={{
                position: 'absolute',
                top: (hour - GRID_START) * HOUR_HEIGHT + 6,
                left: 0,
                width: '100%',
                textAlign: 'right',
                paddingRight: 8,
                fontSize: 12,
                color: 'var(--text-muted)',
              }}>
                {hour}:00
              </div>
            ))}
          </div>

          {/* Day columns */}
          {DAYS.map(day => (
            <div key={day} style={{
              flex: 1,
              position: 'relative',
              height: GRID_HEIGHT,
              borderRight: '1px solid var(--border-color)',
              backgroundColor: 'var(--bg-card)',
            }}>
              {/* Hour divider lines */}
              {Array.from({ length: GRID_HOURS }, (_, i) => i).map(i => (
                <div key={i} style={{
                  position: 'absolute',
                  top: i * HOUR_HEIGHT,
                  left: 0,
                  right: 0,
                  height: 1,
                  backgroundColor: 'var(--border-color)',
                }} />
              ))}

              {/* Slot cards */}
              {layoutByDay[day].map(({ slot, columnIndex, totalColumns, isConflict }) => {
                const cardTop = (timeToHour(slot.start_time) - GRID_START) * HOUR_HEIGHT;
                const cardHeight = Math.max(
                  (timeToHour(slot.end_time) - timeToHour(slot.start_time)) * HOUR_HEIGHT,
                  HOUR_HEIGHT * 0.9
                );
                const cardColor = getCardColor(slot.section_type);
                const isLab = slot.section_type.toUpperCase() === 'LAB';
                const showFull = cardHeight >= 60;

                return (
                  <div
                    key={`${slot.course_code}-${slot.section_number}-${slot.start_time}`}
                    onMouseEnter={e => {
                      e.currentTarget.style.transform = 'scale(1.03)';
                      e.currentTarget.style.zIndex = '20';
                      e.currentTarget.style.boxShadow = '0 8px 24px rgba(0,0,0,0.3)';
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.transform = 'scale(1)';
                      e.currentTarget.style.zIndex = '5';
                      e.currentTarget.style.boxShadow = 'var(--shadow)';
                    }}
                    style={{
                      position: 'absolute',
                      top: cardTop,
                      left: `calc(${(columnIndex / totalColumns) * 100}%)`,
                      width: `calc(${100 / totalColumns}% - 4px)`,
                      height: cardHeight,
                      backgroundColor: cardColor,
                      borderRadius: 4,
                      borderLeft: isConflict ? '4px solid #f44336' : '4px solid transparent',
                      opacity: isConflict ? 0.92 : 1,
                      overflow: 'hidden',
                      boxSizing: 'border-box',
                      zIndex: 5,
                      cursor: 'default',
                      transition: 'transform 0.15s ease, box-shadow 0.15s ease',
                      boxShadow: 'var(--shadow)',
                    }}
                  >
                    {isLab && (
                      <div style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(0,0,0,0.35)', pointerEvents: 'none' }} />
                    )}
                    <div style={{
                      position: 'absolute',
                      top: 8,
                      left: 8,
                      right: 8,
                      bottom: 14,
                      overflow: 'hidden',
                      color: isConflict ? '#f44336' : '#fff',
                      fontSize: 13,
                      lineHeight: 1.4,
                    }}>
                      {showFull ? (
                        <>
                          <div>
                            <span style={{ fontWeight: 'bold', fontSize: 14 }}>{slot.course_code}</span>
                            <span style={{
                              color: isConflict ? 'rgba(244,67,54,0.7)' : 'rgba(255,255,255,0.6)',
                              fontSize: 12,
                              marginLeft: 6,
                            }}>{slot.section_number}</span>
                          </div>
                          <div style={{ fontSize: 12 }}>{slot.instructor_name}</div>
                          <div style={{ fontSize: 11, fontStyle: 'italic', display: 'flex', alignItems: 'center', gap: 3 }}>
                            {slot.is_online ? (
                              <>
                                <Globe size={11} strokeWidth={1.8} />
                                {t('schedule.online')}
                              </>
                            ) : slot.location}
                          </div>
                        </>
                      ) : (
                        <div style={{ fontWeight: 'bold', fontSize: 14 }}>{slot.course_code}</div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

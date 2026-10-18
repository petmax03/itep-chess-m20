"""Operator accounting; no chess decisions or evaluation."""
from .forced_play import ForcedPlay
COMMANDS_PER_MINUTE = 1_200_000
DEFAULT_BUDGET = 3_000_000_000
CONTINUE_BUDGET = 20_000_000_000
BUDGET_CHOICES = (DEFAULT_BUDGET, 10_000_000_000, CONTINUE_BUDGET)


def minutes(commands):
    return commands / COMMANDS_PER_MINUTE


def format_time(commands):
    value = minutes(commands)
    if value > 120:
        return f'{value / 60:.2f}'.replace('.', ',') + ' ч'
    return f'{value:.2f}'.replace('.', ',') + ' мин'


def completed_record(answer, attempts=(), requested_depth=None, budget=DEFAULT_BUDGET):
    requested_depth = requested_depth or answer['depth']
    final = dict(status='answered', budget=budget, steps=answer['steps'],
                 nodes=answer['nodes'], depth=answer['depth'], seconds=answer['seconds'],
                 forced_play=answer.get('forced_play'))
    attempts = [*attempts, final]
    total = sum(a['steps'] for a in attempts)
    return {**answer, 'requested_depth': requested_depth,
            'depth_reduced': answer['depth'] < requested_depth,
            'attempts': attempts, 'total_steps': total,
            'm20_minutes': minutes(answer['steps']),
            'm20_time': format_time(answer['steps']),
            'total_m20_minutes': minutes(total), 'total_m20_time': format_time(total)}


def pgn_comment(record):
    text = (f"М-20: {record['nodes']} позиций; {record['steps']} команд; "
            f"{format_time(record['steps'])}. "
            f"[%m20_nodes {record['nodes']}] [%m20_commands {record['steps']}] "
            f"[%m20_minutes {minutes(record['steps']):.6f}] [%m20_depth {record['depth']}] "
            f"[%m20_requested_depth {record['requested_depth']}] "
            f"[%m20_forced {ForcedPlay.from_metadata(record.get('forced_play')).tag()}]")
    if record.get('depth_reduced'):
        text += (f" Глубина снижена с {record['requested_depth']} до {record['depth']} после лимита."
                 f" [%m20_reduced_from {record['requested_depth']}]")
    for depth in record.get('fallback_depths', [record['depth']] if record.get('depth_reduced') else []):
        text += f' [%m20_fallback {depth}]'
    for extension in record.get('extensions', []):
        text += f" [%m20_extension {extension['extra']}]"
    if record.get('resume_replayed'):
        text += ' После перезапуска приложения расчёт повторён от корня. [%m20_replay 1]'
    if len(record.get('attempts', [])) > 1:
        text += (f" С учётом повторных расчётов: {record['total_steps']} команд, "
                 f"{format_time(record['total_steps'])}. "
                 f"[%m20_total_commands {record['total_steps']}] "
                 f"[%m20_total_minutes {minutes(record['total_steps']):.6f}] "
                 f"[%m20_retries {len(record['attempts'])-1}]")
        modes=[ForcedPlay.from_metadata(a.get('forced_play')).tag() for a in record['attempts']]
        if len(set(modes))>1:text+=' Варианты попыток: '+' → '.join(modes)+'.'
    return text

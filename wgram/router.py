"""Сопоставление входящих обновлений с зарегистрированными обработчиками.

Срабатывает ровно ОДИН обработчик - самый подходящий. Порядок проверки:
  1. точные команды ("/start")
  2. обработчики с state=... (по своим уровням)
  3. остальные по уровням: точный текст -> regex -> starts -> contains -> kind -> fallback
При равном уровне побеждает тот, кто зарегистрирован раньше.
"""

import re
from typing import Any, Callable, Dict, List, Optional

from .types import ALL_KINDS, MEDIA_KINDS

ANY_STATE = "*"     # state=wgram.ANY_STATE: пользователь в любом состоянии

LEVEL_EXACT = 10
LEVEL_REGEX = 30
LEVEL_STARTS = 40
LEVEL_CONTAINS = 50
LEVEL_KIND = 60
LEVEL_FALLBACK = 70
_TEXT_EXACT = 20


def as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set, frozenset)):
        return list(value)
    return [value]


def normalize_command(text: str) -> str:
    """'/Start@my_bot арг' -> '/start'."""
    parts = text.split()
    first = parts[0] if parts else text
    return first.split("@")[0].lower()


class Rule:
    __slots__ = ("handler", "level", "tier", "order", "checks")

    def __init__(self, handler, level, tier, order, checks):
        self.handler = handler
        self.level = level
        self.tier = tier
        self.order = order
        self.checks = checks


def _users_check(users):
    ids = set()
    names = set()
    for u in as_list(users):
        if isinstance(u, int):
            ids.add(u)
        else:
            names.add(str(u).lstrip("@").lower())

    def check(obj, state):
        user = getattr(obj, "user", None)
        if user is None:
            return False
        return user.id in ids or bool(user.username and user.username.lower() in names)
    return check


def _state_check(state_value):
    wanted = [s for s in as_list(state_value)]

    def check(obj, state):
        if ANY_STATE in wanted:
            return state is not None
        return state in wanted
    return check


class Router:
    def __init__(self):
        self._rules: Dict[str, List[Rule]] = {}
        self._counter = 0

    def _push(self, target, handler, level, tier, checks) -> Rule:
        if not callable(handler):
            raise TypeError("Обработчик должен быть функцией")
        rule = Rule(handler, level, tier, self._counter, checks)
        self._counter += 1
        rules = self._rules.setdefault(target, [])
        rules.append(rule)
        rules.sort(key=lambda r: (r.tier, r.level, r.order))
        return rule

    # ---------------------------------------------------------- сообщения

    def add_message(self, target, handler, triggers=(), contains=None, starts=None,
                    regex=None, kind=None, state=None, users=None, chat=None,
                    ignore_case=False) -> Rule:
        """Регистрирует обработчик сообщений.

        triggers/contains/starts/regex - способы сопоставить текст, достаточно любого.
        kind/state/users/chat - ограничения, должны выполняться все.
        """
        level = LEVEL_FALLBACK
        tier = 2
        matchers = []

        cmds, texts = set(), set()
        for t in triggers:
            if not isinstance(t, str) or not t:
                raise TypeError("Триггер должен быть непустой строкой, а не {!r}".format(t))
            if t.startswith("/"):
                cmds.add(normalize_command(t))
            else:
                texts.add(t.lower() if ignore_case else t)
        if cmds or texts:
            def m_exact(obj):
                if cmds and obj.command in cmds:
                    return True
                if texts and obj.text:
                    return (obj.text.lower() if ignore_case else obj.text) in texts
                return False
            matchers.append(m_exact)
            if cmds:
                level = min(level, LEVEL_EXACT)
                tier = 0
            if texts:
                level = min(level, _TEXT_EXACT)

        sub = [s for s in as_list(contains)]
        if sub:
            sub_l = [s.lower() for s in sub] if ignore_case else sub

            def m_contains(obj):
                t = obj.text.lower() if ignore_case else obj.text
                return bool(t) and any(s in t for s in sub_l)
            matchers.append(m_contains)
            level = min(level, LEVEL_CONTAINS)

        pre = [s for s in as_list(starts)]
        if pre:
            pre_l = tuple(s.lower() for s in pre) if ignore_case else tuple(pre)

            def m_starts(obj):
                t = obj.text.lower() if ignore_case else obj.text
                return bool(t) and t.startswith(pre_l)
            matchers.append(m_starts)
            level = min(level, LEVEL_STARTS)

        if regex is not None:
            rx = re.compile(regex, re.IGNORECASE) if isinstance(regex, str) and ignore_case \
                else (re.compile(regex) if isinstance(regex, str) else regex)

            def m_regex(obj):
                if not obj.text:
                    return False
                m = rx.search(obj.text)
                if m:
                    obj.match = m
                return m is not None
            matchers.append(m_regex)
            level = min(level, LEVEL_REGEX)

        checks = []
        if matchers:
            checks.append(lambda obj, st, ms=tuple(matchers): any(m(obj) for m in ms))

        kinds = []
        for k in as_list(kind):
            if k == "media":
                kinds.extend(MEDIA_KINDS)
            elif k in ALL_KINDS:
                kinds.append(k)
            else:
                raise ValueError("Неизвестный kind {!r}. Доступны: {}, media".format(
                    k, ", ".join(ALL_KINDS)))
        if kinds:
            kset = set(kinds)
            checks.append(lambda obj, st: obj.kind in kset)
            level = min(level, LEVEL_KIND)

        types = set()
        for c in as_list(chat):
            if c == "group":
                types.update(("group", "supergroup"))
            elif c in ("private", "supergroup", "channel"):
                types.add(c)
            else:
                raise ValueError("chat должен быть 'private', 'group', 'supergroup' или 'channel'")
        if types:
            checks.append(lambda obj, st: obj.chat.type in types)

        if users is not None:
            checks.append(_users_check(users))
        if state is not None:
            checks.append(_state_check(state))
            if tier != 0:
                tier = 1
        return self._push(target, handler, level, tier, checks)

    # ---------------------------------------------------------- кнопки

    def add_button(self, handler, data=(), prefix=None, regex=None, state=None,
                   users=None) -> Rule:
        level = LEVEL_FALLBACK
        tier = 2
        matchers = []
        exact = set(str(d) for d in data)
        if exact:
            matchers.append(lambda obj: obj.data in exact)
            level = LEVEL_EXACT
            tier = 0
        prefixes = tuple(str(p) for p in as_list(prefix))
        if prefixes:
            def m_prefix(obj):
                for p in prefixes:
                    if obj.data.startswith(p):
                        obj.arg = obj.data[len(p):]
                        return True
                return False
            matchers.append(m_prefix)
            level = min(level, LEVEL_STARTS)
        if regex is not None:
            rx = re.compile(regex) if isinstance(regex, str) else regex

            def m_regex(obj):
                m = rx.search(obj.data)
                if m:
                    obj.match = m
                return m is not None
            matchers.append(m_regex)
            level = min(level, LEVEL_REGEX)
        checks = []
        if matchers:
            checks.append(lambda obj, st, ms=tuple(matchers): any(m(obj) for m in ms))
        if users is not None:
            checks.append(_users_check(users))
        if state is not None:
            checks.append(_state_check(state))
            if tier != 0:
                tier = 1
        return self._push("callback", handler, level, tier, checks)

    # ---------------------------------------------------------- прочие

    def add_plain(self, target, handler, state=None, users=None) -> Rule:
        checks = []
        if users is not None:
            checks.append(_users_check(users))
        tier = 2
        if state is not None:
            checks.append(_state_check(state))
            tier = 1
        return self._push(target, handler, LEVEL_FALLBACK, tier, checks)

    # ---------------------------------------------------------- поиск

    def find(self, target: str, obj: Any, state: Optional[str]) -> Optional[Rule]:
        """Возвращает самое подходящее правило или None."""
        for rule in self._rules.get(target, ()):
            for attr in ("match", "arg"):
                if hasattr(obj, attr):
                    setattr(obj, attr, None)
            if all(check(obj, state) for check in rule.checks):
                return rule
        return None

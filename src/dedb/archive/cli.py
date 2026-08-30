"""The archive app contributes no CLI commands of its own - archive.org
items are handled entirely through the generic target-driven commands
(`dedb run|download|import|rm archive://<id>`; see dedb.verbs and
dedb.archive.backend). This module exists only so dedb.core.get_apps()
has a `commands` list to read."""

commands: list = []

from forgeai.plugins.base import ForgePlugin


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, ForgePlugin] = {}

    def register(self, plugin: ForgePlugin) -> None:
        self._plugins[plugin.name] = plugin

    def get(self, name: str) -> ForgePlugin:
        return self._plugins[name]

    def all(self) -> list[ForgePlugin]:
        return list(self._plugins.values())

    def enabled(self) -> list[ForgePlugin]:
        return [plugin for plugin in self._plugins.values() if plugin.enabled_by_default]


registry = PluginRegistry()

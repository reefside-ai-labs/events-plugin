using Jellyfin.Plugin.Events.Domain;
using MediaBrowser.Model.Plugins;

namespace Jellyfin.Plugin.Events.Configuration;

public class PluginConfiguration : BasePluginConfiguration
{
    public int Revision { get; set; }

    public List<EventDefinition> Events { get; set; } = [];
}

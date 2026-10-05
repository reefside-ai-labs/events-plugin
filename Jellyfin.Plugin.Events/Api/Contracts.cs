using Jellyfin.Plugin.Events.Domain;
using MediaBrowser.Model.Dto;

namespace Jellyfin.Plugin.Events.Api;

public sealed class ConfigurationRequest
{
    public int Revision { get; set; }

    public List<EventDefinition> Events { get; set; } = [];
}

public sealed record EventSummary(Guid Id, string Title, string Description, string ScheduleType, string StartDate, string EndDate, Guid? ArtworkItemId, int ItemCount);

public sealed record EventFeed(string ServerTimeZone, DateOnly Date, IReadOnlyList<EventSummary> Events);

public sealed record EventItems(EventSummary Event, IReadOnlyList<BaseItemDto> Items, int TotalRecordCount, int StartIndex);

public sealed record OverlapWarning(Guid FirstEventId, string FirstTitle, Guid SecondEventId, string SecondTitle, DateOnly Start, DateOnly End, bool RepeatsAnnually);

public sealed record SelectionDiagnostic(Guid ItemId, string Label, string Status);

public sealed record EventDiagnostics(Guid EventId, IReadOnlyList<SelectionDiagnostic> Items, string? ArtworkStatus);

public sealed record AdminConfiguration(int Revision, string ServerTimeZone, DateOnly Date, IReadOnlyList<EventDefinition> Events, IReadOnlyList<OverlapWarning> Warnings, IReadOnlyList<EventDiagnostics> Diagnostics);

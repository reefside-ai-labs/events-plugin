namespace Jellyfin.Plugin.Events.Domain;

/// <summary>A curated promotion; media membership does not modify library metadata.</summary>
public class EventDefinition
{
    public Guid Id { get; set; } = Guid.NewGuid();

    public string Title { get; set; } = string.Empty;

    public string Description { get; set; } = string.Empty;

    public bool Enabled { get; set; } = true;

    /// <summary>Annual (MM-dd) or OneTime (yyyy-MM-dd), with inclusive endpoints.</summary>
    public string ScheduleType { get; set; } = "Annual";

    public string StartDate { get; set; } = "12-01";

    public string EndDate { get; set; } = "12-31";

    public Guid? ArtworkItemId { get; set; }

    /// <summary>Position in this list is the curator's display order.</summary>
    public List<ItemSelection> Items { get; set; } = [];
}

public class ItemSelection
{
    public Guid ItemId { get; set; }

    /// <summary>Saved display label allows administrators to identify a deleted item.</summary>
    public string Label { get; set; } = string.Empty;
}

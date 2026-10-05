namespace Jellyfin.Plugin.Events.Domain;

public static class EventValidation
{
    public static List<string> Validate(IReadOnlyList<EventDefinition> events)
    {
        var errors = new List<string>();
        if (events.Count > 200)
        {
            errors.Add("At most 200 events are supported.");
        }

        var ids = new HashSet<Guid>();
        foreach (var definition in events)
        {
            if (definition is null)
            {
                errors.Add("An event cannot be null.");
                continue;
            }

            var name = string.IsNullOrWhiteSpace(definition.Title) ? "Untitled event" : definition.Title;
            if (definition.Id == Guid.Empty || !ids.Add(definition.Id))
            {
                errors.Add($"{name}: event IDs must be unique and nonempty.");
            }

            if (string.IsNullOrWhiteSpace(definition.Title) || definition.Title.Length > 200)
            {
                errors.Add($"{name}: title must contain 1–200 characters.");
            }

            if (definition.Description is null || definition.Description.Length > 4000)
            {
                errors.Add($"{name}: description must be at most 4000 characters.");
            }

            var scheduleError = EventCalendar.ValidateSchedule(definition);
            if (scheduleError is not null)
            {
                errors.Add($"{name}: {scheduleError}");
            }

            if (definition.Items is null || definition.Items.Count > 5000)
            {
                errors.Add($"{name}: provide a list of at most 5000 items.");
            }
            else if (definition.Items.Any(x => x is null || x.ItemId == Guid.Empty || x.Label is null || x.Label.Length > 500))
            {
                errors.Add($"{name}: selections need a nonempty item ID and a label of at most 500 characters.");
            }
        }

        return errors;
    }

    public static void Normalize(EventDefinition definition)
    {
        definition.Title = definition.Title.Trim();
        definition.Description = definition.Description.Trim();
        definition.Items = definition.Items.DistinctBy(x => x.ItemId).ToList();
    }
}

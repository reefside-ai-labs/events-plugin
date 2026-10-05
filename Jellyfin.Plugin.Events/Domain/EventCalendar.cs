using System.Globalization;

namespace Jellyfin.Plugin.Events.Domain;

/// <summary>Pure date logic. The caller supplies the server-local date or a preview date.</summary>
public static class EventCalendar
{
    public static bool IsActive(EventDefinition definition, DateOnly date)
    {
        if (!definition.Enabled || ValidateSchedule(definition) is not null)
        {
            return false;
        }

        if (definition.ScheduleType == "OneTime")
        {
            return date >= ParseDate(definition.StartDate) && date <= ParseDate(definition.EndDate);
        }

        var day = (date.Month * 100) + date.Day;
        var start = AnnualDay(definition.StartDate);
        var end = AnnualDay(definition.EndDate);
        return start <= end ? day >= start && day <= end : day >= start || day <= end;
    }

    public static string? ValidateSchedule(EventDefinition definition)
    {
        if (definition.ScheduleType == "Annual")
        {
            // A non-leap year rejects February 29 without silently moving a boundary.
            if (!DateOnly.TryParseExact("2001-" + definition.StartDate, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out _)
                || !DateOnly.TryParseExact("2001-" + definition.EndDate, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out _))
            {
                return "Annual dates must be valid MM-dd values; February 29 is not supported.";
            }
        }
        else if (definition.ScheduleType == "OneTime")
        {
            if (!DateOnly.TryParseExact(definition.StartDate, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out var start)
                || !DateOnly.TryParseExact(definition.EndDate, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out var end)
                || end < start)
            {
                return "One-time dates must be valid yyyy-MM-dd values with end on or after start.";
            }
        }
        else
        {
            return "ScheduleType must be Annual or OneTime.";
        }

        return null;
    }

    /// <summary>Finds an example overlapping occurrence, including mixed recurrence types.</summary>
    public static DateWindow? FindOverlap(EventDefinition first, EventDefinition second, DateOnly today)
    {
        if (!first.Enabled || !second.Enabled || ValidateSchedule(first) is not null || ValidateSchedule(second) is not null)
        {
            return null;
        }

        if (first.ScheduleType == "OneTime" && second.ScheduleType == "OneTime")
        {
            return Intersect(new(ParseDate(first.StartDate), ParseDate(first.EndDate)), new(ParseDate(second.StartDate), ParseDate(second.EndDate)));
        }

        if (first.ScheduleType == "OneTime" || second.ScheduleType == "OneTime")
        {
            var once = first.ScheduleType == "OneTime" ? first : second;
            var annual = first.ScheduleType == "Annual" ? first : second;
            var window = new DateWindow(ParseDate(once.StartDate), ParseDate(once.EndDate));
            for (var year = Math.Max(1, window.Start.Year - 1); year <= window.End.Year; year++)
            {
                var overlap = Intersect(window, AnnualWindow(annual, year));
                if (overlap is not null)
                {
                    return overlap;
                }
            }

            return null;
        }

        // Two recurring schedules: find the next/current example around this year.
        var candidates = new List<DateWindow>();
        for (var year = Math.Max(1, today.Year - 1); year <= Math.Min(9999, today.Year + 1); year++)
        {
            for (var otherYear = Math.Max(1, year - 1); otherYear <= Math.Min(9999, year + 1); otherYear++)
            {
                var overlap = Intersect(AnnualWindow(first, year), AnnualWindow(second, otherYear));
                if (overlap is not null)
                {
                    candidates.Add(overlap);
                }
            }
        }

        return candidates.OrderBy(x => x.Start).FirstOrDefault(x => x.End >= today) ?? candidates.OrderByDescending(x => x.End).FirstOrDefault();
    }

    private static DateOnly ParseDate(string value) => DateOnly.ParseExact(value, "yyyy-MM-dd", CultureInfo.InvariantCulture);

    private static int AnnualDay(string value)
    {
        var date = ParseDate("2001-" + value);
        return (date.Month * 100) + date.Day;
    }

    private static DateWindow AnnualWindow(EventDefinition definition, int year)
    {
        var start = ParseDate(year.ToString("D4", CultureInfo.InvariantCulture) + "-" + definition.StartDate);
        var wraps = AnnualDay(definition.EndDate) < AnnualDay(definition.StartDate);
        var end = wraps && year == 9999 ? DateOnly.MaxValue : ParseDate((year + (wraps ? 1 : 0)).ToString("D4", CultureInfo.InvariantCulture) + "-" + definition.EndDate);
        return new(start, end);
    }

    private static DateWindow? Intersect(DateWindow a, DateWindow b)
    {
        var start = a.Start > b.Start ? a.Start : b.Start;
        var end = a.End < b.End ? a.End : b.End;
        return start <= end ? new(start, end) : null;
    }
}

public sealed record DateWindow(DateOnly Start, DateOnly End);

using System.Globalization;
using Jellyfin.Plugin.Events.Domain;
using Xunit;

namespace Jellyfin.Plugin.Events.Tests;

public class EventCalendarTests
{
    private static EventDefinition Annual(string start, string end) => new() { Title = "Event", StartDate = start, EndDate = end };

    private static EventDefinition Once(string start, string end) => new() { Title = "Once", ScheduleType = "OneTime", StartDate = start, EndDate = end };

    [Theory]
    [InlineData("2026-11-30", false)]
    [InlineData("2026-12-01", true)]
    [InlineData("2026-12-31", true)]
    [InlineData("2027-01-01", false)]
    [InlineData("2028-12-15", true)]
    public void ChristmasIsInclusiveAndRecurs(string date, bool expected)
    {
        Assert.Equal(expected, EventCalendar.IsActive(Annual("12-01", "12-31"), DateOnly.Parse(date, CultureInfo.InvariantCulture)));
    }

    [Theory]
    [InlineData("2026-12-14", false)]
    [InlineData("2026-12-15", true)]
    [InlineData("2027-01-05", true)]
    [InlineData("2027-01-06", false)]
    [InlineData("2027-07-01", false)]
    public void CrossYearRangeWraps(string date, bool expected)
    {
        Assert.Equal(expected, EventCalendar.IsActive(Annual("12-15", "01-05"), DateOnly.Parse(date, CultureInfo.InvariantCulture)));
    }

    [Fact]
    public void EqualDatesMeanOneDay()
    {
        var definition = Annual("10-31", "10-31");
        Assert.True(EventCalendar.IsActive(definition, new(2026, 10, 31)));
        Assert.False(EventCalendar.IsActive(definition, new(2026, 10, 30)));
        Assert.False(EventCalendar.IsActive(definition, new(2026, 11, 1)));
    }

    [Fact]
    public void OneTimeDoesNotRepeatAndAllowsLeapDay()
    {
        var definition = Once("2028-02-29", "2028-03-01");
        Assert.Null(EventCalendar.ValidateSchedule(definition));
        Assert.True(EventCalendar.IsActive(definition, new(2028, 2, 29)));
        Assert.True(EventCalendar.IsActive(definition, new(2028, 3, 1)));
        Assert.False(EventCalendar.IsActive(definition, new(2029, 3, 1)));
    }

    [Theory]
    [InlineData("02-29", "03-01")]
    [InlineData("12-01", "02-29")]
    [InlineData("13-01", "12-31")]
    [InlineData("2-01", "12-31")]
    public void InvalidAnnualBoundaryIsRejected(string start, string end)
    {
        var definition = Annual(start, end);
        Assert.NotNull(EventCalendar.ValidateSchedule(definition));
        Assert.False(EventCalendar.IsActive(definition, new(2028, 2, 29)));
    }

    [Fact]
    public void DisabledAndInvalidSchedulesAreInactive()
    {
        var definition = Annual("01-01", "12-31");
        definition.Enabled = false;
        Assert.False(EventCalendar.IsActive(definition, new(2026, 10, 4)));
        Assert.NotNull(EventCalendar.ValidateSchedule(Once("2026-12-31", "2026-12-01")));
        definition.ScheduleType = "Weekly";
        Assert.NotNull(EventCalendar.ValidateSchedule(definition));
    }

    [Fact]
    public void WholeYearIncludesLeapDayWithoutLeapBoundary()
    {
        Assert.True(EventCalendar.IsActive(Annual("01-01", "12-31"), new(2028, 2, 29)));
    }

    [Fact]
    public void AnnualOverlapFindsCrossYearIntersection()
    {
        var overlap = EventCalendar.FindOverlap(Annual("12-15", "01-05"), Annual("01-01", "01-31"), new(2026, 10, 4));
        Assert.Equal(new DateWindow(new(2027, 1, 1), new(2027, 1, 5)), overlap);
    }

    [Fact]
    public void AdjacentRangesDoNotOverlapButSharedBoundaryDoes()
    {
        Assert.Null(EventCalendar.FindOverlap(Annual("10-01", "10-15"), Annual("10-16", "10-31"), new(2026, 10, 4)));
        var overlap = EventCalendar.FindOverlap(Annual("10-01", "10-15"), Annual("10-15", "10-31"), new(2026, 10, 4));
        Assert.Equal(new DateWindow(new(2026, 10, 15), new(2026, 10, 15)), overlap);
    }

    [Fact]
    public void MixedOverlapWorksBeyondCurrentYear()
    {
        var annual = Annual("12-15", "01-05");
        var once = Once("2040-01-01", "2040-01-03");
        var expected = new DateWindow(new(2040, 1, 1), new(2040, 1, 3));
        Assert.Equal(expected, EventCalendar.FindOverlap(annual, once, new(2026, 10, 4)));
        Assert.Equal(expected, EventCalendar.FindOverlap(once, annual, new(2026, 10, 4)));
        Assert.Null(EventCalendar.FindOverlap(annual, Once("2040-07-01", "2040-07-03"), new(2026, 10, 4)));
    }

    [Fact]
    public void OneTimeOverlapAndDisabledOverlap()
    {
        var first = Once("2026-10-01", "2026-10-10");
        var second = Once("2026-10-10", "2026-10-20");
        Assert.Equal(new DateWindow(new(2026, 10, 10), new(2026, 10, 10)), EventCalendar.FindOverlap(first, second, new(2026, 10, 4)));
        second.Enabled = false;
        Assert.Null(EventCalendar.FindOverlap(first, second, new(2026, 10, 4)));
    }

    [Fact]
    public void NormalizationDeduplicatesAndPreservesFirstSelectionOrder()
    {
        var first = Guid.NewGuid();
        var second = Guid.NewGuid();
        var definition = Annual("12-01", "12-31");
        definition.Title = " Christmas ";
        definition.Items = [new() { ItemId = first, Label = "First" }, new() { ItemId = second }, new() { ItemId = first, Label = "Duplicate" }];
        EventValidation.Normalize(definition);
        Assert.Equal("Christmas", definition.Title);
        Assert.Equal(new[] { first, second }, definition.Items.Select(x => x.ItemId));
        Assert.Equal("First", definition.Items[0].Label);
    }

    [Fact]
    public void DuplicateEventIdsAndMalformedSelectionsAreRejected()
    {
        var definition = Annual("12-01", "12-31");
        Assert.Contains(EventValidation.Validate([definition, definition]), error => error.Contains("unique", StringComparison.Ordinal));
        definition.Items = [new()];
        Assert.Contains(EventValidation.Validate([definition]), error => error.Contains("nonempty item ID", StringComparison.Ordinal));
        definition.Items = null!;
        Assert.NotEmpty(EventValidation.Validate([definition]));
    }
}

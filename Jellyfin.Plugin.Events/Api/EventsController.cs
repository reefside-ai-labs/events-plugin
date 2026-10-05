using Jellyfin.Data.Enums;
using Jellyfin.Database.Implementations.Entities;
using Jellyfin.Plugin.Events.Domain;
using MediaBrowser.Controller.Dto;
using MediaBrowser.Controller.Entities;
using MediaBrowser.Controller.Entities.Movies;
using MediaBrowser.Controller.Entities.TV;
using MediaBrowser.Controller.Library;
using MediaBrowser.Controller.Net;
using MediaBrowser.Model.Dto;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.ModelBinding;
using Microsoft.Extensions.DependencyInjection;

namespace Jellyfin.Plugin.Events.Api;

[ApiController]
[Authorize]
[Route("Events")]
public class EventsController(ILibraryManager library, IAuthorizationContext authorization, IDtoService dtoService) : ControllerBase
{
    private static readonly object SaveLock = new();

    [HttpGet("Active")]
    public async Task<ActionResult<EventFeed>> Active()
    {
        var user = await CurrentUser().ConfigureAwait(false);
        if (user is null)
        {
            return Unauthorized();
        }

        Response.Headers.CacheControl = "private, no-store";
        return BuildFeed(user, ServerDate());
    }

    [HttpGet("{id:guid}/Items")]
    public async Task<ActionResult<EventItems>> Items(Guid id, [FromQuery] int startIndex = 0, [FromQuery] int limit = 50)
    {
        var user = await CurrentUser().ConfigureAwait(false);
        if (user is null)
        {
            return Unauthorized();
        }

        Response.Headers.CacheControl = "private, no-store";
        return BuildItems(user, id, ServerDate(), startIndex, limit);
    }

    [HttpGet("Configuration")]
    [Authorize(Policy = "RequiresElevation")]
    public ActionResult<AdminConfiguration> Configuration()
    {
        Response.Headers.CacheControl = "private, no-store";
        return BuildConfiguration();
    }

    [HttpPost("Validate")]
    [Authorize(Policy = "RequiresElevation")]
    public ActionResult<AdminConfiguration> Validate(ConfigurationRequest request)
    {
        var errors = request.Events is null ? ["Events must be a list."] : EventValidation.Validate(request.Events);
        if (errors.Count != 0)
        {
            return BadRequest(new { Errors = errors });
        }

        return BuildConfiguration(new Configuration.PluginConfiguration { Revision = request.Revision, Events = request.Events! });
    }

    [HttpPut("Configuration")]
    [Authorize(Policy = "RequiresElevation")]
    public ActionResult<AdminConfiguration> Save(ConfigurationRequest request)
    {
        var errors = request.Events is null ? ["Events must be a list."] : EventValidation.Validate(request.Events);
        if (errors.Count != 0)
        {
            return BadRequest(new { Errors = errors });
        }

        foreach (var definition in request.Events!)
        {
            EventValidation.Normalize(definition);
            foreach (var selection in definition.Items)
            {
                var item = library.GetItemById(selection.ItemId);
                if (item is not null && item is not Movie && item is not Episode)
                {
                    errors.Add($"{definition.Title}: only movies and individual episodes can be selected.");
                }
                else if (item is not null)
                {
                    selection.Label = Label(item);
                }
            }
        }

        if (errors.Count != 0)
        {
            return BadRequest(new { Errors = errors });
        }

        lock (SaveLock)
        {
            var plugin = Plugin.Instance!;
            if (request.Revision != plugin.Configuration.Revision)
            {
                return Conflict(new { Errors = new[] { "Events changed in another session. Reload before saving." } });
            }

            plugin.UpdateConfiguration(new Configuration.PluginConfiguration
            {
                Revision = plugin.Configuration.Revision + 1,
                Events = request.Events!,
            });
            return BuildConfiguration();
        }
    }

    [HttpGet("Search")]
    [Authorize(Policy = "RequiresElevation")]
    public async Task<ActionResult<IReadOnlyList<BaseItemDto>>> Search([FromQuery] string term = "", [FromQuery] int startIndex = 0)
    {
        if (term.Length > 200 || startIndex < 0)
        {
            return BadRequest();
        }

        var user = await CurrentUser().ConfigureAwait(false);
        if (user is null)
        {
            return Unauthorized();
        }

        var items = library.GetItemList(new InternalItemsQuery(user)
        {
            Recursive = true,
            IncludeItemTypes = [BaseItemKind.Movie, BaseItemKind.Episode],
            SearchTerm = term,
            StartIndex = startIndex,
            Limit = 50,
        });
        return Ok(items.Where(x => x.IsVisible(user)).Select(x => ToDto(x, user)).ToList());
    }

    [HttpGet("Preview")]
    [Authorize(Policy = "RequiresElevation")]
    public async Task<ActionResult<EventFeed>> Preview([FromQuery, BindRequired] DateOnly date, [FromQuery] Guid? userId = null)
    {
        var user = await PreviewUser(userId).ConfigureAwait(false);
        if (user is null)
        {
            return NotFound();
        }

        Response.Headers.CacheControl = "private, no-store";
        return BuildFeed(user, date);
    }

    [HttpGet("Preview/{id:guid}/Items")]
    [Authorize(Policy = "RequiresElevation")]
    public async Task<ActionResult<EventItems>> PreviewItems(Guid id, [FromQuery, BindRequired] DateOnly date, [FromQuery] Guid? userId = null, [FromQuery] int startIndex = 0, [FromQuery] int limit = 50)
    {
        var user = await PreviewUser(userId).ConfigureAwait(false);
        if (user is null)
        {
            return NotFound();
        }

        Response.Headers.CacheControl = "private, no-store";
        return BuildItems(user, id, date, startIndex, limit);
    }

    private static DateOnly ServerDate() => DateOnly.FromDateTime(DateTime.Now);

    private async Task<User?> CurrentUser() => (await authorization.GetAuthorizationInfo(HttpContext).ConfigureAwait(false)).User;

    private async Task<User?> PreviewUser(Guid? userId)
    {
        if (userId is null)
        {
            return await CurrentUser().ConfigureAwait(false);
        }

        return HttpContext.RequestServices.GetRequiredService<IUserManager>().GetUserById(userId.Value);
    }

    private EventFeed BuildFeed(User user, DateOnly date)
    {
        var events = new List<EventSummary>();
        foreach (var definition in Plugin.Instance!.Configuration.Events)
        {
            if (!EventCalendar.IsActive(definition, date))
            {
                continue;
            }

            var items = VisibleItems(definition, user);
            if (items.Count > 0)
            {
                events.Add(Summary(definition, user, items.Count));
            }
        }

        return new(TimeZoneInfo.Local.Id, date, events);
    }

    private ActionResult<EventItems> BuildItems(User user, Guid id, DateOnly date, int startIndex, int limit)
    {
        if (startIndex < 0 || limit is < 1 or > 200)
        {
            return BadRequest(new { Errors = new[] { "StartIndex must be nonnegative; Limit must be between 1 and 200." } });
        }

        var definition = Plugin.Instance!.Configuration.Events.FirstOrDefault(x => x.Id == id);
        if (definition is null || !EventCalendar.IsActive(definition, date))
        {
            return NotFound();
        }

        var items = VisibleItems(definition, user);
        if (items.Count == 0)
        {
            return NotFound();
        }

        return new EventItems(Summary(definition, user, items.Count), items.Skip(startIndex).Take(limit).Select(x => ToDto(x, user)).ToList(), items.Count, startIndex);
    }

    private List<BaseItem> VisibleItems(EventDefinition definition, User user)
    {
        var result = new List<BaseItem>();
        foreach (var selection in definition.Items.DistinctBy(x => x.ItemId))
        {
            var item = library.GetItemById<BaseItem>(selection.ItemId, user);
            if ((item is Movie || item is Episode) && item.IsVisible(user))
            {
                result.Add(item);
            }
        }

        return result;
    }

    private EventSummary Summary(EventDefinition definition, User user, int count)
    {
        Guid? artworkId = null;
        if (definition.ArtworkItemId is { } id)
        {
            var artwork = library.GetItemById<BaseItem>(id, user);
            if (artwork is not null && artwork.IsVisible(user))
            {
                artworkId = id;
            }
        }

        return new(definition.Id, definition.Title, definition.Description, definition.ScheduleType, definition.StartDate, definition.EndDate, artworkId, count);
    }

    private BaseItemDto ToDto(BaseItem item, User user) => dtoService.GetBaseItemDto(item, new DtoOptions(), user);

    private AdminConfiguration BuildConfiguration(Configuration.PluginConfiguration? config = null)
    {
        config ??= Plugin.Instance!.Configuration;
        var date = ServerDate();
        var warnings = new List<OverlapWarning>();
        for (var i = 0; i < config.Events.Count; i++)
        {
            for (var j = i + 1; j < config.Events.Count; j++)
            {
                var first = config.Events[i];
                var second = config.Events[j];
                var overlap = EventCalendar.FindOverlap(first, second, date);
                if (overlap is not null)
                {
                    warnings.Add(new(first.Id, first.Title, second.Id, second.Title, overlap.Start, overlap.End, first.ScheduleType == "Annual" && second.ScheduleType == "Annual"));
                }
            }
        }

        var diagnostics = config.Events.Select(definition => new EventDiagnostics(
            definition.Id,
            definition.Items.Select(selection =>
            {
                var item = library.GetItemById(selection.ItemId);
                return new SelectionDiagnostic(selection.ItemId, item is null ? selection.Label : Label(item), item is null ? "Missing" : item is Movie || item is Episode ? "Available" : "Unsupported");
            }).ToList(),
            definition.ArtworkItemId is { } id && library.GetItemById(id) is null ? "Missing" : null)).ToList();
        return new(config.Revision, TimeZoneInfo.Local.Id, date, config.Events, warnings, diagnostics);
    }

    private static string Label(BaseItem item) => item is Episode episode
        ? $"{episode.SeriesName} · S{episode.ParentIndexNumber:00}E{episode.IndexNumber:00} · {episode.Name}"
        : $"{item.Name}{(item.ProductionYear is { } year ? $" ({year})" : string.Empty)}";
}

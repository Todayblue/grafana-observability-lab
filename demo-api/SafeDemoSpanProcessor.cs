using System.Diagnostics;
using OpenTelemetry;

// The demo accepts untrusted HTTP headers, URL and query strings. Keep only
// bounded semantic tags from auto-instrumented server spans and child spans.
internal sealed class SafeDemoSpanProcessor : BaseProcessor<Activity>
{
    private static readonly HashSet<string> AllowedTags = new(StringComparer.Ordinal)
    {
        "http.route",
        "http.request.method",
        "http.response.status_code",
        "network.protocol.version",
        "url.scheme"
    };

    public override void OnEnd(Activity activity)
    {
        foreach (var tag in activity.TagObjects.ToArray())
        {
            if (!AllowedTags.Contains(tag.Key))
            {
                activity.SetTag(tag.Key, null);
            }
        }

        // Do not export an exception message through the span status description.
        if (!string.IsNullOrEmpty(activity.StatusDescription))
        {
            activity.SetStatus(activity.Status);
        }
    }
}

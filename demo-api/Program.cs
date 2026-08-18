using System.Diagnostics;
using OpenTelemetry.Exporter;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;
using Prometheus;

const string DemoApiActivitySourceName = "DemoApi";
using var demoApiActivitySource = new ActivitySource(DemoApiActivitySourceName);

if (args.Contains("--healthcheck", StringComparer.Ordinal))
{
    using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(2) };
    try
    {
        using var response = await client.GetAsync("http://127.0.0.1:8080/healthz");
        Environment.ExitCode = response.IsSuccessStatusCode ? 0 : 1;
    }
    catch
    {
        Environment.ExitCode = 1;
    }
    return;
}

var builder = WebApplication.CreateBuilder(args);
var otlpEndpoint = builder.Configuration["OTEL_EXPORTER_OTLP_ENDPOINT"] ?? "http://alloy:4317";
builder.Services.AddOpenTelemetry()
    .ConfigureResource(resource => resource.AddService(serviceName: "demo-api"))
    .WithTracing(tracing => tracing
        .AddSource(DemoApiActivitySourceName)
        .AddAspNetCoreInstrumentation()
        .AddOtlpExporter(options =>
        {
            options.Protocol = OtlpExportProtocol.Grpc;
            options.Endpoint = new Uri(otlpEndpoint);
        }));

builder.Logging.ClearProviders();
builder.Logging.AddJsonConsole(options =>
{
    options.IncludeScopes = true;
    options.TimestampFormat = "yyyy-MM-dd'T'HH:mm:ss.fff'Z'";
    options.UseUtcTimestamp = true;
});

var app = builder.Build();

var demoHttpRequests = Metrics.CreateCounter(
    "demo_http_requests_total",
    "Total number of requests to demo endpoints.",
    new CounterConfiguration
    {
        LabelNames = new[] { "endpoint", "status_code" }
    });

var demoHttpRequestDuration = Metrics.CreateHistogram(
    "demo_http_request_duration_seconds",
    "Duration of requests to demo endpoints in seconds.",
    new HistogramConfiguration
    {
        LabelNames = new[] { "endpoint" },
        Buckets = new[] { 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0 }
    });

var demoHttpRequestsInProgress = Metrics.CreateGauge(
    "demo_http_requests_in_progress",
    "Number of requests currently in progress for demo endpoints.",
    new GaugeConfiguration
    {
        LabelNames = new[] { "endpoint" }
    });

app.Use(async (context, next) =>
{
    var endpoint = context.Request.Path.Value switch
    {
        "/ok" => "/ok",
        "/slow" => "/slow",
        "/error" => "/error",
        _ => null
    };

    if (endpoint is null)
    {
        await next(context);
        return;
    }

    var inProgress = demoHttpRequestsInProgress.WithLabels(endpoint);
    var stopwatch = System.Diagnostics.Stopwatch.StartNew();
    inProgress.Inc();

    try
    {
        await next(context);
    }
    finally
    {
        stopwatch.Stop();
        inProgress.Dec();
        demoHttpRequestDuration.WithLabels(endpoint).Observe(stopwatch.Elapsed.TotalSeconds);
        demoHttpRequests.WithLabels(endpoint, context.Response.StatusCode.ToString()).Inc();

        var durationMs = stopwatch.Elapsed.TotalMilliseconds;
        if (context.Response.StatusCode >= StatusCodes.Status500InternalServerError)
        {
            app.Logger.LogError(
                "{eventName}: endpoint={endpoint} statusCode={statusCode} durationMs={durationMs}",
                "request_completed",
                endpoint,
                context.Response.StatusCode,
                durationMs);
        }
        else
        {
            app.Logger.LogInformation(
                "{eventName}: endpoint={endpoint} statusCode={statusCode} durationMs={durationMs}",
                "request_completed",
                endpoint,
                context.Response.StatusCode,
                durationMs);
        }
    }
});

// Record request duration and count metrics. Group all 2xx, 3xx, 4xx,
// and 5xx responses together to avoid creating a separate metric series
// for every individual HTTP status code.
app.UseHttpMetrics(options =>
{
    options.ReduceStatusCodeCardinality();
});

app.MapGet("/ok", () =>
    Results.Ok(new { message = "OK" }));

app.MapGet("/slow", async () =>
{
    var delayMs = Random.Shared.Next(300, 1501);
    var validationDelayMs = Math.Max(1, delayMs / 5);
    var responseDelayMs = Math.Max(1, delayMs / 10);
    var workDelayMs = delayMs - validationDelayMs - responseDelayMs;

    using (demoApiActivitySource.StartActivity("ValidateRequest"))
    {
        await Task.Delay(validationDelayMs);
    }

    using (demoApiActivitySource.StartActivity("SimulatedWork"))
    {
        await Task.Delay(workDelayMs);
    }

    using (demoApiActivitySource.StartActivity("BuildResponse"))
    {
        await Task.Delay(responseDelayMs);
    }

    return Results.Ok(new
    {
        message = "Completed after a delay",
        delayMs
    });
});

app.MapGet("/error", () =>
    Results.Json(
        new { message = "A deterministic demo error occurred" },
        statusCode: StatusCodes.Status500InternalServerError));

app.MapGet("/healthz", () =>
    Results.Ok(new { status = "healthy" }));

// prometheus-net serves metrics in the Prometheus text format at /metrics.
app.MapMetrics();

app.Run();

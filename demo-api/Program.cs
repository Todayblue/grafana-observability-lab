using System.Diagnostics;
using OpenTelemetry;
using OpenTelemetry.Exporter;
using OpenTelemetry.Logs;
using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;

const string DemoApiActivitySourceName = "DemoApi";
const string RequestLogCategory = "DemoApi.Requests";
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
var otlpEndpoint = new Uri(builder.Configuration["OTEL_EXPORTER_OTLP_ENDPOINT"] ?? "http://lgtm:4317");
var appVersion = builder.Configuration["OTEL_SERVICE_VERSION"];
if (string.IsNullOrWhiteSpace(appVersion))
{
    throw new InvalidOperationException("OTEL_SERVICE_VERSION must identify the Demo API version.");
}

// Emit only the allowlisted request-completion event. Do not forward framework
// diagnostics, exception messages, URLs or arbitrary request values to either sink.
builder.Logging.ClearProviders();
builder.Logging.AddFilter((_, category, level) =>
    category == RequestLogCategory && level >= LogLevel.Information);
builder.Logging.AddJsonConsole(options =>
{
    options.IncludeScopes = false;
    options.TimestampFormat = "yyyy-MM-dd'T'HH:mm:ss.fff'Z'";
    options.UseUtcTimestamp = true;
});

builder.Services.AddOpenTelemetry()
    .ConfigureResource(resource => resource
        .AddService("demo-api", serviceVersion: appVersion, autoGenerateServiceInstanceId: false)
        .AddAttributes(new Dictionary<string, object>
        {
            ["deployment.environment.name"] = "lab"
        }))
    .WithMetrics(metrics => metrics
        .AddMeter("Microsoft.AspNetCore.Hosting")
        .AddView("http.server.request.duration", new ExplicitBucketHistogramConfiguration
        {
            // Seconds; includes the 300-1500 ms /slow workload.
            Boundaries = new double[] {
                0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25,
                0.5, 0.75, 1, 1.5, 2.5, 5, 7.5, 10
            }
        })
        .AddOtlpExporter(options =>
        {
            options.Protocol = OtlpExportProtocol.Grpc;
            options.Endpoint = otlpEndpoint;
        }))
    .WithTracing(tracing => tracing
        .SetSampler(new AlwaysOnSampler())
        .AddSource(DemoApiActivitySourceName)
        .AddAspNetCoreInstrumentation(options =>
        {
            options.Filter = context =>
                context.Request.Path.Value is "/ok" or "/slow" or "/error";
            options.RecordException = false;
        })
        .AddProcessor(new SafeDemoSpanProcessor())
        .AddOtlpExporter(options =>
        {
            options.Protocol = OtlpExportProtocol.Grpc;
            options.Endpoint = otlpEndpoint;
        }))
    .WithLogging(logging => logging
        .AddOtlpExporter(options =>
        {
            options.Protocol = OtlpExportProtocol.Grpc;
            options.Endpoint = otlpEndpoint;
        }));

var app = builder.Build();
var requestLogger = app.Services.GetRequiredService<ILoggerFactory>()
    .CreateLogger(RequestLogCategory);
var requestCompletedEvent = new EventId(1000, "request_completed");

app.Use(async (context, next) =>
{
    var route = context.Request.Path.Value switch
    {
        "/ok" => "/ok",
        "/slow" => "/slow",
        "/error" => "/error",
        _ => null
    };

    if (route is null)
    {
        await next(context);
        return;
    }

    var stopwatch = Stopwatch.StartNew();
    try
    {
        await next(context);
    }
    finally
    {
        stopwatch.Stop();
        var statusCode = context.Response.StatusCode;
        if (statusCode >= StatusCodes.Status500InternalServerError)
        {
            // A deliberate HTTP 500 is an error span, not a fabricated exception.
            Activity.Current?.SetStatus(ActivityStatusCode.Error);
        }

        var level = statusCode >= 500 ? LogLevel.Error
            : statusCode >= 400 ? LogLevel.Warning : LogLevel.Information;

        // This log executes while the ASP.NET request Activity is still current.
        // OpenTelemetry supplies its TraceId/SpanId; never invent correlation IDs.
        requestLogger.Log(level, requestCompletedEvent,
            "request_completed event.name={event.name} http.route={http.route} http.response.status_code={http.response.status_code} duration_ms={duration_ms}",
            "request_completed", route, statusCode, stopwatch.Elapsed.TotalMilliseconds);
    }
});

app.MapGet("/ok", () => Results.Ok(new { message = "OK" }));

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

    return Results.Ok(new { message = "Completed after a delay", delayMs });
});

app.MapGet("/error", () =>
    Results.Json(new { message = "A deterministic demo error occurred" },
        statusCode: StatusCodes.Status500InternalServerError));

app.MapGet("/healthz", () => Results.Ok(new { status = "healthy" }));

app.Run();

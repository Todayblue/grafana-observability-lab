FROM mcr.microsoft.com/dotnet/sdk:8.0.423 AS build
WORKDIR /src

COPY demo-api.csproj ./
RUN dotnet restore demo-api.csproj

COPY . ./
RUN dotnet publish demo-api.csproj \
    --configuration Release \
    --output /app/publish \
    --no-restore \
    /p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:8.0.29 AS runtime
WORKDIR /app

COPY --from=build /app/publish ./

# .NET 8 Linux images provide an unprivileged user through APP_UID.
USER $APP_UID
EXPOSE 8080

ENTRYPOINT ["dotnet", "demo-api.dll"]

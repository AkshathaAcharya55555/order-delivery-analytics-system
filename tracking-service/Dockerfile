# Multi-stage build: compile with Maven+JDK17, run with a slim JRE.
# Tests are not re-run during this build (already verified via `mvn test`
# on the host); skip only to keep image builds fast and deterministic.

FROM maven:3.9.9-eclipse-temurin-17 AS build
WORKDIR /build
COPY pom.xml .
RUN mvn -q -B dependency:go-offline
COPY src ./src
RUN mvn -q -B package -DskipTests

FROM eclipse-temurin:17-jre-alpine
WORKDIR /app
COPY --from=build /build/target/*.jar app.jar
EXPOSE 8083
ENTRYPOINT ["java", "-jar", "/app/app.jar"]

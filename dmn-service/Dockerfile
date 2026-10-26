# Stage 1: build with Maven (Kogito code generation + tests skipped for image speed)
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /build
COPY pom.xml .
RUN mvn -B -q dependency:go-offline || true
COPY src ./src
RUN mvn -B -q package -DskipTests

# Stage 2: slim runtime
FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /build/target/dmn-service-1.0.0-SNAPSHOT.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]

package org.acme;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.swagger.v3.core.util.Json;
import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.media.Schema;
import org.springdoc.core.customizers.OpenApiCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.io.ClassPathResource;

import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.util.Iterator;
import java.util.Map;

/**
 * Inlines the DMN JSON schema that Kogito generates (META-INF/resources/refs/discount.json)
 * into the OpenAPI document, mirroring what the Kogito Quarkus extension does out of the box.
 * <p>
 * Result: components.schemas contains DiscountApprovalInputSet, DiscountApprovalOutputSet and
 * the DMN item definitions (tFacts, tIntent, ...), and the /DiscountApproval operation references
 * them instead of the external "/refs/discount.json#/definitions/InputSet" pointer.
 */
@Configuration
public class DmnOpenApiCustomizer {

    private static final String MODEL_NAME = "DiscountApproval";
    private static final String SCHEMA_RESOURCE = "META-INF/resources/refs/discount.json";
    private static final String EXTERNAL_REF_PREFIX = "/refs/discount.json#/definitions/";
    private static final String LOCAL_REF_PREFIX = "#/definitions/";
    private static final String COMPONENTS_PREFIX = "#/components/schemas/";

    @Bean
    public OpenApiCustomizer inlineDmnSchemas(ObjectMapper mapper) {
        return openApi -> {
            JsonNode definitions = loadDefinitions(mapper);
            if (definitions == null) {
                return;
            }
            Components components = openApi.getComponents() != null ? openApi.getComponents() : new Components();
            openApi.setComponents(components);

            Iterator<Map.Entry<String, JsonNode>> it = definitions.fields();
            while (it.hasNext()) {
                Map.Entry<String, JsonNode> entry = it.next();
                String name = componentName(entry.getKey());
                JsonNode rewritten = rewriteRefs(entry.getValue().deepCopy(), LOCAL_REF_PREFIX);
                Schema<?> schema = Json.mapper().convertValue(rewritten, Schema.class);
                components.addSchemas(name, schema);
            }

            if (openApi.getPaths() != null) {
                openApi.getPaths().values().forEach(pathItem -> pathItem.readOperations().forEach(op -> {
                    if (op.getRequestBody() != null && op.getRequestBody().getContent() != null) {
                        op.getRequestBody().getContent().values().forEach(mt -> relink(mt.getSchema()));
                    }
                    if (op.getResponses() != null) {
                        op.getResponses().values().forEach(resp -> {
                            if (resp.getContent() != null) {
                                resp.getContent().values().forEach(mt -> relink(mt.getSchema()));
                            }
                        });
                    }
                }));
            }
        };
    }

    /** InputSet -> DiscountApprovalInputSet (Kogito/Quarkus naming); item definitions keep their name. */
    private static String componentName(String definitionName) {
        if ("InputSet".equals(definitionName) || "OutputSet".equals(definitionName)) {
            return MODEL_NAME + definitionName;
        }
        return definitionName;
    }

    private static void relink(Schema<?> schema) {
        if (schema != null && schema.get$ref() != null && schema.get$ref().startsWith(EXTERNAL_REF_PREFIX)) {
            String def = schema.get$ref().substring(EXTERNAL_REF_PREFIX.length());
            schema.set$ref(COMPONENTS_PREFIX + componentName(def));
        }
    }

    private static JsonNode rewriteRefs(JsonNode node, String prefix) {
        if (node.isObject()) {
            var obj = (com.fasterxml.jackson.databind.node.ObjectNode) node;
            JsonNode ref = obj.get("$ref");
            if (ref != null && ref.isTextual() && ref.asText().startsWith(prefix)) {
                obj.put("$ref", COMPONENTS_PREFIX + componentName(ref.asText().substring(prefix.length())));
            }
            obj.fields().forEachRemaining(e -> rewriteRefs(e.getValue(), prefix));
        } else if (node.isArray()) {
            node.forEach(child -> rewriteRefs(child, prefix));
        }
        return node;
    }

    private static JsonNode loadDefinitions(ObjectMapper mapper) {
        ClassPathResource resource = new ClassPathResource(SCHEMA_RESOURCE);
        if (!resource.exists()) {
            return null;
        }
        try (InputStream in = resource.getInputStream()) {
            return mapper.readTree(in).get("definitions");
        } catch (IOException e) {
            throw new UncheckedIOException("Cannot read DMN schema " + SCHEMA_RESOURCE, e);
        }
    }
}

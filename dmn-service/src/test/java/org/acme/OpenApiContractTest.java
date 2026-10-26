package org.acme;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class OpenApiContractTest {

    @Autowired
    MockMvc mvc;

    @Test
    void openApiExposesDiscountApprovalInputSet() throws Exception {
        mvc.perform(get("/q/openapi.json"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.paths['/DiscountApproval'].post.requestBody.content['application/json'].schema['$ref']")
                        .value("#/components/schemas/DiscountApprovalInputSet"))
                .andExpect(jsonPath("$.components.schemas.DiscountApprovalInputSet.required[0]").value("facts"))
                .andExpect(jsonPath("$.components.schemas.DiscountApprovalInputSet.properties.facts['$ref']")
                        .value("#/components/schemas/tFacts"))
                .andExpect(jsonPath("$.components.schemas.tIntent.properties.proposed_discount_pct.type").value("number"))
                .andExpect(jsonPath("$.components.schemas.tFacts.properties.credit_hold.type").value("boolean"))
                .andExpect(jsonPath("$.components.schemas.tFacts.properties.tier.type").value("string"));
    }
}

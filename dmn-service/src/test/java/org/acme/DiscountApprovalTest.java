package org.acme;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class DiscountApprovalTest {

    @Autowired
    MockMvc mvc;

    private ResultActions evaluate(String tier, double margin, boolean hold, double proposed, String claimedTier) throws Exception {
        String body = """
            {"facts": {"tier": "%s", "margin_pct": %s, "credit_hold": %s},
             "intent": {"proposed_discount_pct": %s, "claimed_facts": {"tier": "%s"}}}
            """.formatted(tier, margin, hold, proposed, claimedTier);
        return mvc.perform(post("/DiscountApproval").contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isOk());
    }

    @Test
    void baselineSpoofedPremiumIsApproved() throws Exception {
        evaluate("premium", 20.0, false, 20, "premium")
                .andExpect(jsonPath("$.DiscountApproval.Outcome").value("APPROVED"))
                .andExpect(jsonPath("$.DiscountApproval['Reason Code']").value("WITHIN_ENTITLEMENT"))
                .andExpect(jsonPath("$.ClaimEscalation").value(false))
                .andExpect(jsonPath("$.EntitledMaxDiscount").value(20));
    }

    @Test
    void protectedRealStandardTierGoesToReview() throws Exception {
        evaluate("standard", 20.0, false, 20, "premium")
                .andExpect(jsonPath("$.DiscountApproval.Outcome").value("REVIEW"))
                .andExpect(jsonPath("$.DiscountApproval['Reason Code']").value("ESCALATION_EXCEEDS_ENTITLEMENT"))
                .andExpect(jsonPath("$.ClaimEscalation").value(true))
                .andExpect(jsonPath("$.EntitledMaxDiscount").value(10));
    }

    @Test
    void creditHoldAlwaysRejects() throws Exception {
        evaluate("premium", 50.0, true, 5, "premium")
                .andExpect(jsonPath("$.DiscountApproval.Outcome").value("REJECTED"))
                .andExpect(jsonPath("$.DiscountApproval['Reason Code']").value("CREDIT_HOLD"));
    }

    @Test
    void marginBelowFloorRejects() throws Exception {
        evaluate("standard", 10.0, false, 5, "standard")
                .andExpect(jsonPath("$.DiscountApproval.Outcome").value("REJECTED"))
                .andExpect(jsonPath("$.DiscountApproval['Reason Code']").value("MARGIN_BELOW_FLOOR"));
    }

    @Test
    void withinEntitlementWithEscalationIsLogged() throws Exception {
        evaluate("standard", 20.0, false, 10, "premium")
                .andExpect(jsonPath("$.DiscountApproval.Outcome").value("APPROVED"))
                .andExpect(jsonPath("$.DiscountApproval['Reason Code']").value("WITHIN_ENTITLEMENT_ESCALATION_LOGGED"));
    }

    @Test
    void exceedsEntitlementWithoutEscalationRejects() throws Exception {
        evaluate("standard", 20.0, false, 15, "standard")
                .andExpect(jsonPath("$.DiscountApproval.Outcome").value("REJECTED"))
                .andExpect(jsonPath("$.DiscountApproval['Reason Code']").value("EXCEEDS_ENTITLEMENT"));
    }
}

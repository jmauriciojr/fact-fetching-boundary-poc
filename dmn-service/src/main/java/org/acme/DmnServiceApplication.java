package org.acme;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Kogito generates the DMN REST controller under a package derived from the DMN namespace
 * ("org.acme.dmn" becomes "org_46acme_46dmn", with dots escaped) and its runtime beans under
 * org.kie.kogito.app. All three roots must be scanned for the /DiscountApproval endpoint to exist.
 */
@SpringBootApplication(scanBasePackages = {"org.acme", "org.kie.kogito", "org_46acme_46dmn"})
public class DmnServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(DmnServiceApplication.class, args);
    }
}

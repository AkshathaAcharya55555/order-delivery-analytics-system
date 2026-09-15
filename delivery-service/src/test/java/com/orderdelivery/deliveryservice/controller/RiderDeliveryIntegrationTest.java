package com.orderdelivery.deliveryservice.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.orderdelivery.deliveryservice.dto.CreateRiderRequest;
import com.orderdelivery.deliveryservice.dto.UpdateAvailabilityRequest;
import com.orderdelivery.deliveryservice.dto.UpdateDeliveryStatusRequest;
import com.orderdelivery.deliveryservice.model.DeliveryStatus;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * Runs against the real, already-running oda_postgres database using data
 * seeded by database/seed.sql: order 5 (Emma Wilson, Portland, status
 * CANCELLED — used as a negative case) and a fresh order/rider created
 * directly via JDBC per test so assignment has a real order to target.
 * @Transactional rolls back every test.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class RiderDeliveryIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    private CreateRiderRequest riderRequest(String city) {
        CreateRiderRequest request = new CreateRiderRequest();
        request.setFirstName("Test");
        request.setLastName("Rider");
        request.setPhone("555-0000");
        request.setVehicleType("bike");
        request.setCity(city);
        request.setRating(new BigDecimal("4.5"));
        return request;
    }

    private Long insertReadyOrder(String city, Long locationId) {
        Long customerId = jdbcTemplate.queryForObject(
                "SELECT customer_id FROM customers LIMIT 1", Long.class);
        return jdbcTemplate.queryForObject(
                "INSERT INTO orders (customer_id, delivery_location_id, status, order_placed_at, total_amount, payment_method) " +
                        "VALUES (?, ?, 'READY_FOR_PICKUP', now(), 10.00, 'card') RETURNING order_id",
                Long.class, customerId, locationId);
    }

    private Long insertLocation(String city, double lat, double lon) {
        return jdbcTemplate.queryForObject(
                "INSERT INTO locations (address_line, city, state, latitude, longitude) " +
                        "VALUES ('1 Test St', ?, 'TX', ?, ?) RETURNING location_id",
                Long.class, city, lat, lon);
    }

    @Test
    void createRider_thenListRiders_includesIt() throws Exception {
        String response = mockMvc.perform(post("/api/riders")
                        .contentType("application/json")
                        .content(objectMapper.writeValueAsString(riderRequest("Austin"))))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.available").value(true))
                .andReturn().getResponse().getContentAsString();

        Long riderId = objectMapper.readTree(response).get("riderId").asLong();

        // Sort by riderId descending rather than assuming the new rider (a
        // freshly-autoincremented, and therefore numerically highest, id)
        // falls on an arbitrary early page - the riders table now also holds
        // the full ~2,000-row synthetic dataset loaded for the analytics
        // phase, so a fixed page=0/size=500 with no sort is no longer a safe
        // assumption (a rider with an id in the 2000s can fall past page 0
        // once total rows exceed 500 with default DB-order sorting).
        mockMvc.perform(get("/api/riders").param("page", "0").param("size", "5")
                        .param("sort", "riderId,desc"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content[?(@.riderId == " + riderId + ")]").exists());
    }

    @Test
    void updateAvailability_togglesFlag() throws Exception {
        String response = mockMvc.perform(post("/api/riders")
                        .contentType("application/json")
                        .content(objectMapper.writeValueAsString(riderRequest("Denver"))))
                .andReturn().getResponse().getContentAsString();
        Long riderId = objectMapper.readTree(response).get("riderId").asLong();

        UpdateAvailabilityRequest req = new UpdateAvailabilityRequest();
        req.setAvailable(false);

        mockMvc.perform(put("/api/riders/{id}/availability", riderId)
                        .contentType("application/json")
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.available").value(false));
    }

    @Test
    void assignDelivery_endToEnd_thenAdvanceStatus() throws Exception {
        Long locationId = insertLocation("Chicago", 41.8781, -87.6298);
        Long orderId = insertReadyOrder("Chicago", locationId);

        mockMvc.perform(post("/api/riders")
                .contentType("application/json")
                .content(objectMapper.writeValueAsString(riderRequest("Chicago"))));

        mockMvc.perform(post("/api/deliveries/{orderId}/assign", orderId))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.deliveryStatus").value("ASSIGNED"))
                .andExpect(jsonPath("$.orderId").value(orderId));

        // assigning a second time must fail — already has a delivery
        mockMvc.perform(post("/api/deliveries/{orderId}/assign", orderId))
                .andExpect(status().isConflict());

        UpdateDeliveryStatusRequest pickedUp = new UpdateDeliveryStatusRequest();
        pickedUp.setStatus(DeliveryStatus.PICKED_UP);
        mockMvc.perform(put("/api/deliveries/{orderId}/status", orderId)
                        .contentType("application/json")
                        .content(objectMapper.writeValueAsString(pickedUp)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.deliveryStatus").value("PICKED_UP"));

        // illegal: PICKED_UP -> DELIVERED directly (must go through OUT_FOR_DELIVERY)
        UpdateDeliveryStatusRequest delivered = new UpdateDeliveryStatusRequest();
        delivered.setStatus(DeliveryStatus.DELIVERED);
        mockMvc.perform(put("/api/deliveries/{orderId}/status", orderId)
                        .contentType("application/json")
                        .content(objectMapper.writeValueAsString(delivered)))
                .andExpect(status().isConflict());

        mockMvc.perform(get("/api/deliveries/{orderId}", orderId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.deliveryStatus").value("PICKED_UP"));
    }

    @Test
    void assignDelivery_noRiderInCity_returns409() throws Exception {
        // A made-up city rather than one of the 6 canonical cities: the
        // riders table now also holds the full synthetic dataset, which has
        // real riders in every canonical city (Austin/Denver/Portland/
        // Chicago/Miami/Seattle) - only a city guaranteed to have zero
        // riders makes this test deterministic.
        Long locationId = insertLocation("Nowhereville", 10.0, 10.0);
        Long orderId = insertReadyOrder("Nowhereville", locationId);

        mockMvc.perform(post("/api/deliveries/{orderId}/assign", orderId))
                .andExpect(status().isConflict());
    }
}

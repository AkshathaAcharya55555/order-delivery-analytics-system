package com.orderdelivery.trackingservice.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.orderdelivery.trackingservice.dto.AddTrackingEventRequest;
import com.orderdelivery.trackingservice.model.OrderStatus;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * Runs against the real, already-running oda_postgres database.
 * @Transactional rolls back every test's inserts.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class TrackingControllerIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    private Long insertPlacedOrder() {
        Long customerId = jdbcTemplate.queryForObject("SELECT customer_id FROM customers LIMIT 1", Long.class);
        Long locationId = jdbcTemplate.queryForObject("SELECT location_id FROM locations LIMIT 1", Long.class);
        Long orderId = jdbcTemplate.queryForObject(
                "INSERT INTO orders (customer_id, delivery_location_id, status, order_placed_at, total_amount, payment_method) " +
                        "VALUES (?, ?, 'PLACED', now(), 10.00, 'card') RETURNING order_id",
                Long.class, customerId, locationId);
        jdbcTemplate.update(
                "INSERT INTO order_status_history (order_id, status, changed_at) VALUES (?, 'PLACED', now())",
                orderId);
        return orderId;
    }

    @Test
    void getTracking_returnsCurrentStatusAndHistory() throws Exception {
        Long orderId = insertPlacedOrder();

        mockMvc.perform(get("/api/orders/{orderId}/tracking", orderId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.orderId").value(orderId))
                .andExpect(jsonPath("$.currentStatus").value("PLACED"))
                .andExpect(jsonPath("$.history.length()").value(1))
                .andExpect(jsonPath("$.history[0].status").value("PLACED"));
    }

    @Test
    void getTracking_missingOrder_returns404() throws Exception {
        mockMvc.perform(get("/api/orders/{orderId}/tracking", 9999999))
                .andExpect(status().isNotFound());
    }

    @Test
    void addEvent_legalTransition_appendsHistoryAndUpdatesStatus() throws Exception {
        Long orderId = insertPlacedOrder();

        AddTrackingEventRequest request = new AddTrackingEventRequest();
        request.setStatus(OrderStatus.CONFIRMED);

        mockMvc.perform(post("/api/orders/{orderId}/tracking", orderId)
                        .contentType("application/json")
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.status").value("CONFIRMED"));

        mockMvc.perform(get("/api/orders/{orderId}/tracking", orderId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.currentStatus").value("CONFIRMED"))
                .andExpect(jsonPath("$.history.length()").value(2));
    }

    @Test
    void addEvent_illegalTransition_returns409() throws Exception {
        Long orderId = insertPlacedOrder();

        AddTrackingEventRequest request = new AddTrackingEventRequest();
        request.setStatus(OrderStatus.DELIVERED); // PLACED cannot jump straight to DELIVERED

        mockMvc.perform(post("/api/orders/{orderId}/tracking", orderId)
                        .contentType("application/json")
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isConflict());
    }
}

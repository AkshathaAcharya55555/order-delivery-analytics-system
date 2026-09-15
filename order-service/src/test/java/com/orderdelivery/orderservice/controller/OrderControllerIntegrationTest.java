package com.orderdelivery.orderservice.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.orderdelivery.orderservice.dto.CreateOrderRequest;
import com.orderdelivery.orderservice.dto.OrderItemRequest;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.List;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * Runs against the real, already-running oda_postgres database (see
 * src/main/resources/application.yml) using the customer/location seeded by
 * database/seed.sql (ids 1-5). @Transactional rolls back every test so no
 * data is left behind.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class OrderControllerIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    private CreateOrderRequest validRequest() {
        CreateOrderRequest request = new CreateOrderRequest();
        request.setCustomerId(1L);
        request.setDeliveryLocationId(1L);
        request.setPaymentMethod("card");

        OrderItemRequest item = new OrderItemRequest();
        item.setProductName("Test Burger");
        item.setCategory("main");
        item.setUnitPrice(new BigDecimal("9.99"));
        item.setQuantity(2);
        request.setItems(List.of(item));
        return request;
    }

    @Test
    void createAndFetchOrder_roundTrips() throws Exception {
        String response = mockMvc.perform(post("/api/orders")
                        .contentType("application/json")
                        .content(objectMapper.writeValueAsString(validRequest())))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.status").value("PLACED"))
                .andExpect(jsonPath("$.totalAmount").value(19.98))
                .andExpect(jsonPath("$.items.length()").value(1))
                .andReturn().getResponse().getContentAsString();

        Long orderId = objectMapper.readTree(response).get("orderId").asLong();

        mockMvc.perform(get("/api/orders/{id}", orderId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.orderId").value(orderId))
                .andExpect(jsonPath("$.customerId").value(1));
    }

    @Test
    void createOrder_unknownCustomer_returns404() throws Exception {
        CreateOrderRequest request = validRequest();
        request.setCustomerId(999999L);

        mockMvc.perform(post("/api/orders")
                        .contentType("application/json")
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isNotFound());
    }

    @Test
    void createOrder_missingItems_returns400() throws Exception {
        CreateOrderRequest request = validRequest();
        request.setItems(List.of());

        mockMvc.perform(post("/api/orders")
                        .contentType("application/json")
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest());
    }

    @Test
    void getOrder_missing_returns404() throws Exception {
        mockMvc.perform(get("/api/orders/{id}", 999999))
                .andExpect(status().isNotFound());
    }

    @Test
    void cancelOrder_thenCancelAgain_secondCallReturns409() throws Exception {
        String response = mockMvc.perform(post("/api/orders")
                        .contentType("application/json")
                        .content(objectMapper.writeValueAsString(validRequest())))
                .andReturn().getResponse().getContentAsString();
        Long orderId = objectMapper.readTree(response).get("orderId").asLong();

        mockMvc.perform(put("/api/orders/{id}/cancel", orderId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("CANCELLED"));

        mockMvc.perform(put("/api/orders/{id}/cancel", orderId))
                .andExpect(status().isConflict());
    }

    @Test
    void listOrders_returnsPage() throws Exception {
        mockMvc.perform(get("/api/orders").param("page", "0").param("size", "5"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content").isArray());
    }
}

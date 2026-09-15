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

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * Bean-validation edge cases for POST /api/orders that
 * OrderControllerIntegrationTest doesn't already cover (unknown customer,
 * empty items). These were previously only checked manually with curl
 * against a running container (see the Docker end-to-end testing phase) -
 * this class turns those into permanent, repeatable assertions.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class OrderValidationTest {

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
        item.setProductName("Test Item");
        item.setCategory("main");
        item.setUnitPrice(new BigDecimal("5.00"));
        item.setQuantity(1);
        request.setItems(List.of(item));
        return request;
    }

    @Test
    void createOrder_invalidPaymentMethod_returns400WithDetail() throws Exception {
        CreateOrderRequest request = validRequest();
        request.setPaymentMethod("bitcoin");

        mockMvc.perform(post("/api/orders")
                        .contentType("application/json")
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.details[0]").value("paymentMethod must be one of: card, cash, wallet, upi"));
    }

    @Test
    void createOrder_negativeQuantity_returns400() throws Exception {
        CreateOrderRequest request = validRequest();
        request.getItems().get(0).setQuantity(-5);

        mockMvc.perform(post("/api/orders")
                        .contentType("application/json")
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.details[0]").value("quantity must be > 0"));
    }

    @Test
    void createOrder_zeroQuantity_returns400() throws Exception {
        CreateOrderRequest request = validRequest();
        request.getItems().get(0).setQuantity(0);

        mockMvc.perform(post("/api/orders")
                        .contentType("application/json")
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest());
    }

    @Test
    void createOrder_negativeUnitPrice_returns400() throws Exception {
        CreateOrderRequest request = validRequest();
        request.getItems().get(0).setUnitPrice(new BigDecimal("-1.00"));

        mockMvc.perform(post("/api/orders")
                        .contentType("application/json")
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.details[0]").value("unitPrice must be >= 0"));
    }

    @Test
    void createOrder_blankProductName_returns400() throws Exception {
        CreateOrderRequest request = validRequest();
        request.getItems().get(0).setProductName("");

        mockMvc.perform(post("/api/orders")
                        .contentType("application/json")
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.details[0]").value("productName is required"));
    }

    @Test
    void createOrder_blankCategory_returns400() throws Exception {
        CreateOrderRequest request = validRequest();
        request.getItems().get(0).setCategory("");

        mockMvc.perform(post("/api/orders")
                        .contentType("application/json")
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.details[0]").value("category is required"));
    }

    @Test
    void createOrder_missingPaymentMethod_returns400() throws Exception {
        CreateOrderRequest request = validRequest();
        request.setPaymentMethod(null);

        mockMvc.perform(post("/api/orders")
                        .contentType("application/json")
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.details[0]").value("paymentMethod is required"));
    }

    @Test
    void createOrder_missingDeliveryLocationId_returns400() throws Exception {
        CreateOrderRequest request = validRequest();
        request.setDeliveryLocationId(null);

        mockMvc.perform(post("/api/orders")
                        .contentType("application/json")
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.details[0]").value("deliveryLocationId is required"));
    }

    @Test
    void createOrder_nonexistentDeliveryLocation_returns404() throws Exception {
        CreateOrderRequest request = validRequest();
        request.setDeliveryLocationId(999999L);

        mockMvc.perform(post("/api/orders")
                        .contentType("application/json")
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isNotFound());
    }
}

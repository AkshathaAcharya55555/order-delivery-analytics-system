package com.orderdelivery.orderservice.controller;

import com.orderdelivery.orderservice.dto.CreateOrderRequest;
import com.orderdelivery.orderservice.dto.OrderResponse;
import com.orderdelivery.orderservice.model.OrderStatus;
import com.orderdelivery.orderservice.service.OrderService;
import jakarta.validation.Valid;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/orders")
public class OrderController {

    private final OrderService orderService;

    public OrderController(OrderService orderService) {
        this.orderService = orderService;
    }

    @PostMapping
    public ResponseEntity<OrderResponse> createOrder(@Valid @RequestBody CreateOrderRequest request) {
        var order = orderService.createOrder(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(OrderResponse.from(order));
    }

    @GetMapping("/{id}")
    public OrderResponse getOrder(@PathVariable Long id) {
        return OrderResponse.from(orderService.getOrder(id));
    }

    @GetMapping
    public Page<OrderResponse> listOrders(
            @RequestParam(required = false) OrderStatus status,
            Pageable pageable) {
        return orderService.listOrders(status, pageable).map(OrderResponse::from);
    }

    @PutMapping("/{id}/cancel")
    public OrderResponse cancelOrder(@PathVariable Long id) {
        return OrderResponse.from(orderService.cancelOrder(id));
    }
}

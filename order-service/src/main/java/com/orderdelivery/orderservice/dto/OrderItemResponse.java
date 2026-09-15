package com.orderdelivery.orderservice.dto;

import java.math.BigDecimal;

public class OrderItemResponse {

    private final Long orderItemId;
    private final String productName;
    private final String category;
    private final BigDecimal unitPrice;
    private final Integer quantity;
    private final BigDecimal lineTotal;

    public OrderItemResponse(Long orderItemId, String productName, String category,
                              BigDecimal unitPrice, Integer quantity, BigDecimal lineTotal) {
        this.orderItemId = orderItemId;
        this.productName = productName;
        this.category = category;
        this.unitPrice = unitPrice;
        this.quantity = quantity;
        this.lineTotal = lineTotal;
    }

    public Long getOrderItemId() {
        return orderItemId;
    }

    public String getProductName() {
        return productName;
    }

    public String getCategory() {
        return category;
    }

    public BigDecimal getUnitPrice() {
        return unitPrice;
    }

    public Integer getQuantity() {
        return quantity;
    }

    public BigDecimal getLineTotal() {
        return lineTotal;
    }
}
